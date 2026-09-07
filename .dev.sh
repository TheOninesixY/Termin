fuser -k 4000/tcp
podman run --rm -v "$PWD":/usr/src/app:Z -p 4000:4000 -it docker.io/starefossen/github-pages
