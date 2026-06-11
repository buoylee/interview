# Docker Fundamentals

Docker packages applications and their dependencies into portable, self-contained images that run consistently across development, CI, and production environments. Understanding how Docker builds images, manages networks, and stores data is essential for writing efficient, reproducible container workflows.

## Image Layers and Build Cache

A Docker image is a stack of read-only layers. Each instruction in a Dockerfile (RUN, COPY, ADD) creates a new layer containing only the filesystem diff produced by that instruction. Layers are identified by a hash of their content and are shared across images that use the same base.

Docker's build cache reuses an existing layer if the instruction and all preceding layers are unchanged. This makes instruction ordering critical for build speed. Instructions that change frequently (copying application source code) should appear after instructions that change rarely (installing system packages). For example, placing RUN apt-get install before COPY src/ means package installation is cached across source changes, keeping incremental builds fast.

A single changed instruction invalidates the cache for that layer and all subsequent layers. Changing a COPY target file invalidates that COPY layer and every RUN layer after it. Keep expensive, stable operations (dependency installation) near the top of the Dockerfile and volatile operations (copying source) near the bottom.

## Multi-Stage Builds

Multi-stage builds allow a single Dockerfile to define multiple FROM stages. Earlier stages act as build environments — they install compilers, build tools, and test dependencies. The final stage copies only the compiled artifacts or runtime files from earlier stages, discarding the build toolchain. This produces dramatically smaller final images without requiring separate Dockerfiles or build scripts.

A common pattern is a builder stage that runs go build or npm run build, and a final stage based on a minimal image (scratch, distroless, or alpine) that copies only the compiled binary or static assets. The final image has no compiler, no source code, and no build-time secrets that may have been passed as build arguments in earlier stages.

## Docker Networks

Docker creates a virtual network for containers and provides several network driver types. The bridge driver (default) creates an isolated virtual network on the host. Containers on the same bridge network can communicate using their container names as DNS hostnames — Docker's embedded DNS resolver maps container names to their IP addresses automatically. Containers on different bridge networks cannot communicate unless explicitly connected.

The host driver removes network isolation and gives the container direct access to the host's network stack. There is no port mapping; the container binds directly to host ports. Host networking offers lower latency and avoids NAT overhead, but the container shares the host's port namespace and is unsuitable for multi-container setups where port conflicts would occur.

## Volumes vs Bind Mounts

Docker provides two mechanisms for persisting data outside a container's writable layer. Volumes are managed by Docker: Docker creates and tracks the storage location (typically under /var/lib/docker/volumes/). Volumes are portable, can be shared between containers, and support volume drivers for remote or cloud-backed storage. They are the recommended approach for persistent application data.

Bind mounts map a specific path on the host filesystem into the container. Any change in the container is immediately visible on the host and vice versa. Bind mounts are useful for development workflows where you want the running container to reflect live source code edits. For production, volumes are preferred because they are independent of host filesystem layout and work correctly across different environments.

## Docker Compose: healthcheck and depends_on

Docker Compose orchestrates multi-container applications defined in a YAML file. The depends_on directive controls startup order, but by default it only waits for the dependent container to start, not for it to be healthy. A database container that is started but still initializing will fail connections from an application container that started immediately after.

The healthcheck instruction (in the Dockerfile or in compose.yml) defines a command Docker runs periodically to assess container health. Once a container reports healthy, Compose (with condition: service_healthy in depends_on) will proceed to start the dependent service. This provides a reliable startup gate without requiring application-level retry logic for transient unavailability during initialization.
