# Sandbox for agent-written code. Every developer/tester run gets a fresh,
# throwaway container from this image. See backend/services/sandbox.py.
#
# Base: Microsoft's official Playwright image (Ubuntu 24.04 "noble") with Node.js
# and browsers preinstalled. Its version must match @playwright/test in
# templates/nextjs-starter/package.json.
FROM mcr.microsoft.com/playwright:v1.64.0-noble

# pnpm installed globally (as root, before switching user) so every user has it,
# pinned to the repo's pnpm version
RUN npm install -g pnpm@10.30.1 && npm cache clean --force

# Agents never run as root. pwuser is the non-root user the base image provides.
USER pwuser
WORKDIR /workspace

# Package downloads go through the npm-only proxy (sandbox/proxy). The sandbox
# network has no other route out, so these are the only way to reach the internet.
ENV HTTP_PROXY=http://npm-proxy:3128 \
    HTTPS_PROXY=http://npm-proxy:3128 \
    http_proxy=http://npm-proxy:3128 \
    https_proxy=http://npm-proxy:3128 \
    NO_PROXY=localhost,127.0.0.1 \
    no_proxy=localhost,127.0.0.1 \
    # Tests run headless; never phone home
    NEXT_TELEMETRY_DISABLED=1 \
    CI=1

CMD ["bash"]
