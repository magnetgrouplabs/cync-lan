# Installation

## Docker
This project is bundled as a docker image, you can build it locally or pull images from DockerHub.

### Build
- Clone the repo 
- `cd` into the repo directory
- `docker compose -f ./docker/Dockerfile build` will output a `baudneo/cync-lan:latest` tagged image
- Copy the example `docker-compose.yaml` file and edit it for your setup.
- Set up env vars using the docker-compose `environment` section or uncomment the `env_file` option and create an .env file

#### Upgrading
- Rebuild the image

### Pull
- Copy the example [`docker-compose.yaml`](../docker/docker-compose.yaml) file
- Set up env vars using the docker-compose `environment` section or uncomment the `env_file` option and create an .env file (See [example](../docker/example.env))
- `docker compose up -d --force-recreate`

#### Upgrading
- `cd` to wherever you have your CyncLAN `docker-compose.yaml` file
- `docker compose pull && docker compose up -d --force-recreate`