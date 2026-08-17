FROM python:3.12-slim

LABEL org.opencontainers.image.title="moltline-mcp" \
      org.opencontainers.image.description="Zero-dependency stdio bridge to Moltline Studio's 14 hosted MCP servers" \
      org.opencontainers.image.source="https://github.com/GarphenGate/moltline-mcp" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app
COPY moltline_mcp.py .

# The bridge speaks MCP over stdio and proxies to the hosted fleet.
# Default server: catalog. Override with e.g. `docker run ... timeops`.
ENTRYPOINT ["python", "moltline_mcp.py"]
CMD ["catalog"]
