# GoGoGo
Final Project for CSCI3280 2025-26 Sem2

## Group Members
| Name          | Student ID |
| ------------- | ---------- |
| Wong Kwok Kam | 1155192018 |
| Peng Minqi    | 1155191548 |
| Lim Xuan Qing | 1155264390 |

## Prerequisites
- [Docker](https://www.docker.com/) & Docker Compose
- [Git](https://git-scm.com/)

## Development

### 1. Clone the repository
```bash
git clone git@github.com:davidwkk/GoGoGo.git
cd GoGoGo
```

### 2. Set up environment variables
```bash
cp .env.example .env
```
Fill in your API keys in the `.env` file.

### 3. Start all services
```bash
docker-compose up --build
```

| Service  | URL                        |
| -------- | -------------------------- |
| Frontend | http://localhost:5173      |
| Backend  | http://localhost:8000      |
| API Docs | http://localhost:8000/docs |

### 4. Stop services
```bash
docker-compose down
```

> **Note:** To reset the database, run `docker-compose down -v` to remove the persistent volume.
