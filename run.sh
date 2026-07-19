docker rm -f postgres-games

docker run \
    -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_USER=user \
    -e POSTGRES_DB=games \
    -p 5432:5432 \
    --name=postgres-games \
    --network=games \
    -v postgres-data:/var/lib/postgresql/data \
    -d \
    postgres:17

