FROM rust:slim-trixie AS builder

ARG GRIN_REPO=https://github.com/wiesche89/grin.git
ARG GRIN_BRANCH=staging

WORKDIR /usr/src
RUN apt update && apt install -y git libncurses5-dev libncursesw5-dev clang pkg-config
RUN git clone --depth 1 --branch "$GRIN_BRANCH" "$GRIN_REPO" grin
WORKDIR /usr/src/grin
RUN cargo build --release

FROM debian:trixie-slim
RUN apt update && apt install -y ca-certificates libncursesw5-dev && update-ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/src/grin/target/release/grin /usr/local/bin/grin
VOLUME ["/root/.grin"]
EXPOSE 13413 13414
ENTRYPOINT ["grin", "--no-tui"]
CMD ["--testnet", "server", "run"]
