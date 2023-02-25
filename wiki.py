import json
import requests
from typing import List, Optional, Set
from urllib.parse import urlparse


class WikiException(Exception):
    pass


class Metadata:
    def __init__(self, author: str, editor: str, created: str, modified: str) -> None:
        self.author = author
        self.editor = editor
        self.created = created
        self.modified = modified


class Page:
    def __init__(
        self,
        domain: "Domain",
        name: str,
        path: str,
        extension: str,
        back: Optional[str],
        data: str,
        links: List[str],
        metadata: Metadata,
    ) -> None:
        self.domain = domain
        self.name = name
        self.path = path
        self.extension = extension
        self.back = back
        self.data = data
        self.links = links
        self.metadata = metadata


class Domain:
    def __init__(self, root: str, address: str, default: str, error: str) -> None:
        self.root = root
        self.address = address
        self.default = default
        self.error = error
        self.pages: List[Page] = []

    def addPage(
        self,
        name: str,
        path: str,
        extension: str,
        back: Optional[str],
        data: str,
        links: List[str],
        metadata: Metadata,
    ) -> None:
        self.pages.append(
            Page(self, name, path, extension, back, data, links, metadata)
        )

    def getAllPages(self) -> List[Page]:
        return [p for p in self.pages if p.path != self.error]


class Wiki:
    def __init__(self, data: str) -> None:
        # First, see if the data is a valid URI.
        isUrl = False

        try:
            parts = urlparse(data)
            if parts.scheme in {"http", "https"} and parts.netloc:
                isUrl = True
        except Exception:
            pass

        # Now, if it is a valid URI, try to grab it.
        if isUrl:
            try:
                resp = requests.get(data)
                if resp.status_code == 200:
                    data = resp.text
            except requests.exceptions.ConnectionError:
                pass

        # Now, attempt to load the data.
        wikijson = json.loads(data)

        # Now, grab the top level domains.
        self.domains: List[Domain] = []

        # There are some duplicates, which we don't want appearing in random, so filter them
        # out.
        seenPages: Set[str] = set()

        for entry in wikijson:
            domain = Domain(
                root=entry["path"],
                address=entry["address"],
                default=entry["defPage"],
                error=entry["er2Page"],
            )

            # Things that we honestly don't need around.
            if domain.root in {"TESTDOMAIN"}:
                continue

            for page in entry["pages"]:
                name = page["name"]
                path = page["path"]
                extension = page["extension"]
                back = page.get("backpath")
                data = page["data"]
                links = [str(s) for s in page["links"]]

                full_path = f"{domain.root}:{path}"
                if full_path in seenPages:
                    continue
                seenPages.add(full_path)

                meta = page["meta"]
                metadata = Metadata(
                    author=meta["author"],
                    editor=meta["editor"],
                    created=meta["madeTime"],
                    modified=meta["editTime"],
                )

                domain.addPage(
                    name=name,
                    path=path,
                    extension=extension,
                    back=back,
                    data=data,
                    links=links,
                    metadata=metadata,
                )

            self.domains.append(domain)

        # Create a virtual page for connection errors.
        self.nonexistant = Domain(
            root="LOCAL.ERR",
            address="00.00",
            default="",
            error="",
        )
        self.nonexistant.addPage(
            name="Connection Error",
            path="",
            extension="INT",
            back=None,
            data="connerr",
            links=[],
            metadata=Metadata(
                author="nobody",
                editor="nobody",
                created="never",
                modified="never",
            ),
        )

        # Create a virtual page for command help.
        self.help = Domain(
            root="LOCAL.HELP",
            address="00.00",
            default="",
            error="",
        )
        self.help.addPage(
            name="Command Line Help",
            path="",
            extension="INT",
            back=None,
            data="help",
            links=["NX.HELP:/MAIN/COMHELP"],
            metadata=Metadata(
                author="nobody",
                editor="nobody",
                created="never",
                modified="never",
            ),
        )

    def getPage(self, uri: str) -> Page:
        if ":" in uri:
            domain, path = uri.split(":", 1)
        else:
            domain = uri
            path = None

        # Start with the nonexistant domain, adjust its root to the domain we're going for.
        found = self.nonexistant
        found.root = domain

        for existing in [*self.domains, self.help]:
            if existing.root == domain:
                found = existing
                break

        if path is None:
            path = found.default

        # Now, try to find this page.
        for page in found.pages:
            if page.path == path:
                return page
            if page.extension and (page.path + "." + page.extension) == path:
                return page

        # If we couldn't find the page, return the error page.
        for page in found.pages:
            if page.path == found.error:
                return page

        raise WikiException(
            "Path "
            + uri
            + " resolves to a domain with no valid path and no valid error page!"
        )

    def getAllPages(self, domain: Optional[str] = None) -> List[Page]:
        pages: List[Page] = []

        for dom in self.domains:
            if domain is not None and domain != dom.root:
                continue

            pages.extend(p for p in dom.pages if p.path != dom.error)

        return pages
