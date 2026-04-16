# Docksmith-Team13
Cloud Computing Project to build a simplified version of docker from scratch 

# 🚀 Docksmith – A Lightweight Container Engine

Docksmith is a simplified containerization system inspired by Docker. It is built from scratch using Python and Linux primitives to demonstrate how container engines work internally.

---

## 📌 Features

* 🔧 Build images from a `Docksmithfile`
* 📦 Layered filesystem using tar archives
* ⚡ Build caching with cache hit/miss detection
* 🔁 Cache invalidation on file changes
* 🐳 Run containers with filesystem isolation (`chroot`)
* 🌱 Environment variable support
* 📁 Image management (list & remove)
* 🌐 Web-based UI for interaction

---

## 🧠 Project Architecture

```
UI (Flask)
   ↓
CLI (docksmith.py)
   ↓
Build Engine (engine.py)
   ↓
Storage (layers + manifest)
   ↓
Runtime (container execution)
```

---

## 🏗️ Supported Instructions

Docksmith supports the following instructions:

* `FROM` – Load base image
* `COPY` – Copy files into image
* `RUN` – Execute commands inside container
* `WORKDIR` – Set working directory
* `ENV` – Set environment variables
* `CMD` – Define default execution command

---

## ⚙️ Installation & Setup

### 1. Clone Repository

```
git clone <your-repo-url>
cd Docksmith
```

### 2. Setup Environment (WSL/Linux recommended)

```
sudo apt update
sudo apt install -y python3 python3-venv util-linux
```

### 3. Create Virtual Environment

```
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies

```
pip install flask --break-system-packages
```

---

## ▶️ Usage

### 🔹 Import Base Image

```
python3 import_base.py alpine:3.18 alpine.tar
```

---

### 🔹 Build Image

```
python3 docksmith.py build -t myapp:latest sample_app/
```

---

### 🔹 List Images

```
python3 docksmith.py images
```

---

### 🔹 Run Container

```
python3 docksmith.py run myapp:latest
```

---

### 🔹 Remove Image

```
python3 docksmith.py rmi myapp:latest
```

---

## 🌐 Web UI

Run the UI:

```
python ui.py
```

Open in browser:

```
http://127.0.0.1:5000
```

Features:

* Build images
* Run containers
* View images
* Delete images
* View logs/output

---

## 🧪 Example Docksmithfile

```
FROM alpine:3.18

WORKDIR /app

ENV GREETING=Hello
ENV APP_VERSION=1.0.0

COPY . /app

RUN sh -c "echo Build complete"

CMD ["sh", "/app/run.sh"]
```

---

## 🔍 Key Concepts

### 📦 Layers

* Each `COPY` and `RUN` creates a layer
* Stored as `.tar` files
* Identified using SHA-256 hashes

---

### ⚡ Cache

* Reuses layers if inputs unchanged
* Cache key includes:

  * instruction
  * previous layer
  * file content
* Supports cache invalidation

---

### 🐳 Runtime

* Builds root filesystem from layers
* Uses `chroot` for isolation
* Executes CMD inside container

---

## 👥 Team Contribution

### 👤 Person A – Storage & Image Management

* Layer storage (SHA256)
* Image manifests
* `images` and `rmi` commands

### 👤 Person B – Runtime

* Container execution
* Filesystem isolation (chroot)
* Environment handling

### 👤 Person C – Build Engine & Cache

* Docksmithfile parsing
* Instruction execution
* Cache system

---

## 🎯 Learning Outcomes

This project demonstrates:

* Container internals
* Filesystem layering
* Content-addressable storage
* Build caching mechanisms
* Linux isolation (chroot, namespaces)
* System design and modular architecture

---

## ⚠️ Notes

* Designed for Linux/WSL (not native Windows)
* Educational project (not production-ready)
* Network isolation not implemented

---

## 🏁 Conclusion

Docksmith provides a hands-on understanding of how container systems like Docker work internally by implementing core features from scratch.

---

## 📜 License

This project is for academic purposes.
