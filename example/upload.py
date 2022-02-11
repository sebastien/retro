from retro import Component, run, on
import os

HTML = """
<html><body>
<form action="/upload" method="post" enctype="multipart/form-data" >
    <label for="name">Upload your file: </label>
    <input type="file" name="file" id="file" required />
    <input type="submit" value="Submit" />
</form>
</body></html>
"""


class Upload(Component):

    @on(GET="/")
    def index(self, request):
        return request.respond(HTML, "text/html")

    # curl -F "image=@PATH_TO_FILE" http://localhost:8000/upload
    @on(POST="upload")
    def upload(self, request):
        request.load()
        file = request.file()
        if not os.path.exists("data"):
            os.makedirs("data")
        path = f"data/{file.filename}"
        with open(path, "wb") as f:
            f.write(file.data)
        print(f"File written to {path}")
        return request.redirect("/")


if __name__ == "__main__":
    run(components=(Upload()))

# EOF
