# The package has an extension module in Rust, so its wheel is built in an image with Rust,
# from GitHub (PYWHAT_REF: a branch, tag or commit), and installed into the Python image
FROM rust:alpine AS build
ARG PYWHAT_REF=main
RUN apk add --no-cache git musl-dev py3-pip python3 \
    && python3 -m pip wheel --no-cache-dir --no-deps --wheel-dir /wheels \
        "git+https://github.com/bee-san/pyWhat@${PYWHAT_REF}"

FROM python:3.10-alpine
COPY --from=build /wheels /wheels
# The extension needs libgcc_s, which the wheels on PyPI carry, but this one doesn't
RUN apk add --no-cache libgcc \
    && pip install --no-cache-dir --only-binary :all: /wheels/*.whl \
    && rm -rf /wheels
WORKDIR /workdir
ENTRYPOINT [ "python", "-m", "pywhat" ]
