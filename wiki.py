import json
import requests
from typing import List, Optional
from urllib.parse import urlparse


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
        back: Optional[str],
        data: str,
        links: List[str],
        metadata: Metadata,
    ) -> None:
        self.domain = domain
        self.name = name
        self.path = path
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
        back: Optional[str],
        data: str,
        links: List[str],
        metadata: Metadata,
    ) -> None:
        self.pages.append(Page(self, name, path, back, data, links, metadata))


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

        for entry in wikijson:
            domain = Domain(
                root=entry["path"],
                address=entry["address"],
                default=entry["defPage"],
                error=entry["er2Page"],
            )

            for page in entry["pages"]:
                name = page["name"]
                path = page["path"]
                back = page.get("backpath")
                data = page["data"]
                links = [str(s) for s in page["links"]]

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
                    back=back,
                    data=data,
                    links=links,
                    metadata=metadata,
                )

            self.domains.append(domain)

        # Create a virtual page for connection errors.
        self.nonexistant = Domain(
            root="unspecified",
            address="00.00",
            default="/ERR",
            error="/ERR",
        )
        self.nonexistant.addPage(
            name="Connection Error",
            path="/ERR",
            back=None,
            data="css\n!Error #8: No connection.\n$Could not establish connection with specified server.",
            links=[],
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

        for existing in self.domains:
            if existing.root == domain:
                found = existing
                break

        if path is None:
            path = found.default

        # Now, try to find this page.
        for page in found.pages:
            if page.path == path:
                return page

        # If we couldn't find the page, return the error page.
        for page in found.pages:
            if page.path == found.error:
                return page

        raise Exception(
            "Path "
            + uri
            + " resolves to a domain with no valid path and no valid error page!"
        )
