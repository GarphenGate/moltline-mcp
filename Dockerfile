FROM python:3.13-alpine

LABEL org.opencontainers.image.title="moltline-mcp" \
      org.opencontainers.image.description="Zero-dependency stdio bridge to Moltline Studio's 19 hosted MCP servers" \
      org.opencontainers.image.source="https://github.com/GarphenGate/moltline-mcp" \
      org.opencontainers.image.licenses="MIT"

# The bridge is standard library only, so the image needs no package manager:
# dropping pip and setuptools removes their vendored packages from the scan
# surface and makes the container unable to install anything at runtime.
RUN python -m pip uninstall -y pip setuptools >/dev/null 2>&1 || true \
    && rm -rf /root/.cache

WORKDIR /app
COPY moltline_mcp.py .
USER nobody

# The bridge speaks MCP over stdio and proxies to the hosted fleet.
# Default server: catalog. Override with e.g. `docker run ... timeops`.
ENTRYPOINT ["python", "moltline_mcp.py"]
CMD ["catalog"]
