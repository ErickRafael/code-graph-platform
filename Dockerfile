# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Builder image – build dwgread from LibreDWG (static)
# ---------------------------------------------------------------------------
FROM debian:bookworm AS builder

ARG LIBREDWG_REF=0.13.3
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential git ca-certificates autoconf automake libtool pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "$LIBREDWG_REF" https://github.com/LibreDWG/libredwg.git /src/libredwg
WORKDIR /src/libredwg

# Generate build system & configure (bindings disabled for speed)
RUN ./autogen.sh && \
    ./configure --enable-release --disable-shared --disable-bindings --disable-python --disable-perl

# Build just the dwgread program (this still links the static lib)
RUN make -j$(nproc)

# ---------------------------------------------------------------------------
# Final runtime image – Python + dwgread
# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm

# Copy the dwgread binary from the builder stage
COPY --from=builder /src/libredwg/programs/.libs/dwgread /usr/local/bin/dwgread
RUN chmod +x /usr/local/bin/dwgread && dwgread --version || true

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 