# **Microservices Architecture – Overview**

This repository showcases a microservices-based architecture for product retrieval, order placement, inventory reservation, and order lifecycle management. The system uses a hybrid model of synchronous REST calls and asynchronous Kafka-based event processing to achieve scalability, resilience, and loose coupling.

---

## 📋 Prerequisites

Ensure the following are installed:

* **Docker Desktop**
- [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)

* **Specmatic Docker Extension**
- [https://hub.docker.com/extensions/specmatic/specmatic-docker-desktop-extension](https://hub.docker.com/extensions/specmatic/specmatic-docker-desktop-extension)

---

## 🔧 Setup

### Clone the project

```shell
git clone https://github.com/specmatic/specmatic-arazzo-async-sample
cd specmatic-arazzo-async-sample
```

---

## 🚀 Running the Project

Start the full stack using Docker Compose:

```shell
docker compose up --build
```

This launches the following services:

| Service           | Port | Description                    |
| ----------------- | ---- | ------------------------------ |
| **Location API**  | 3000 | Provides user location details |
| **Products API**  | 3001 | Returns products by location   |
| **Order API**     | 3002 | Handles order lifecycle        |
| **Warehouse API** | 3003 | Manages inventory operations   |
| **Kafka**         | 9092 | Internal broker port           |
| **Postgres**      | 5432 | Shared database                |

---

## 🗺 Architecture Diagram

![Diagram](./assets/flow.svg)

---

## 🧩 Components

### **Location Service**

* Provides user-specific location details.
* Serves as the authoritative source for user–location mapping.

### **Products Service**

* Fetches products based on a location code.
* Validates product availability before ordering.

### **Order Service**

* Consumes events from Kafka (e.g., `create-orders`).
* Manages the order lifecycle (PENDING → ACCEPTED → OUT_FOR_DELIVERY).
* Publishes order updates back to Kafka.

### **Warehouse Service**

* Reserves and confirms inventory for incoming orders.
* Sends updates back to the Order Service through Kafka.

### **Kafka**

* Backbone for event-driven communication.
* Decouples services for scalable, fault-tolerant workflows.

---

## 🔌 Communication Model

### **Synchronous REST Calls**

Used for immediate operations:

* Fetching location details
* Retrieving available products
* Getting final order status

### **Asynchronous Kafka Events**

Used for background or long-running workflows:

* Order creation
* Inventory reservation
* Delivery status updates

This combination supports resilience, scalability, and eventual consistency.

---

## 📦 Kafka Topics

| Topic                     | Purpose                                    |
| ------------------------- | ------------------------------------------ |
| `create-orders`           | Initiates the order creation workflow      |
| `wip-orders`              | Orders pending inventory confirmation      |
| `accepted-orders`         | Orders successfully confirmed and reserved |
| `out-for-delivery-orders` | Delivery dispatch and tracking workflow    |
