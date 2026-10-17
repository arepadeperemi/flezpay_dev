# FlezPay Business OS

[![Stellar Integration](https://img.shields.io/badge/Stellar-USDC%20%7C%20USDT-10b981?style=flat-square&logo=stellar)](https://stellar.org)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python)](https://python.org)
[![Django 5.0+](https://img.shields.io/badge/Django-5.0+-092e20?style=flat-square&logo=django)](https://djangoproject.com)
[![License: Proprietary / Public Validation](https://img.shields.io/badge/License-Product%20Validation-blue?style=flat-square)](#license)

**FlezPay** is an Africa-first, AI-powered Business Operating System designed for modern retailers. It combines multi-channel Point of Sale (POS), responsive online storefronts, inventory synchronization, automated payroll, AI business intelligence, and next-generation stablecoin payment rails (Stellar & Arc networks).

---

## 🌟 Key Features

### 1. Multi-Rail Crypto & Fiat Checkout
- **Stellar Network Stablecoin Rails**: Accept **USDC** and **USDT** on Stellar with near-instant settlement (< 3 seconds) and negligible fees (< $0.001).
- **Arc Network (Circle CCTP / EVM)**: Cross-chain deposit addresses and ledger listener for automated invoice reconciliation.
- **Pure-Fiat Merchant Experience**: Merchants receive credited fiat balances directly in their dashboard; FlezPay settles on-chain assets with licensed off-ramps (e.g., Yellow Card).
- **Realistic 3-Step Stepper Flow**: Asset selection (`USDT` / `USDC`) ➔ Network selection (`Stellar` / `Arc`) ➔ Payment Details (dynamic QR code, one-click copy, real-time status updates).

### 2. Multi-Storefront Architecture
- 13 distinct storefront design layouts (Grid, List, Editorial, Metro Pulse, Luxe Horizon, Glass Spatial, Vanguard Atelier, and more).
- Dynamic cart, taxes, and promotional discount engine.
- Instant subdomains (`storename.flezpay.com`) and custom domain mapping.

### 3. Comprehensive Business Management
- **Smart POS & QR Terminals**: Retail checkout with instant receipt generation and offline resilience.
- **Inventory & Catalog Management**: Real-time multi-location inventory syncing.
- **AI Business Insights**: Automated sales forecasts, anomaly detection, and automated stock alerts.
- **Staff & Payroll**: Role-based access control, departmental organization, and payroll disbursals.

---

## 🏗️ Architecture & Stellar Building Blocks

```
┌─────────────────────────────────────────────────────────────────┐
│                     Customer (Online or Physical)                │
│  Chooses “Pay with Crypto” → Sends from any Stellar wallet      │
│  to FlezPay deposit address + unique memo/reference             │
└───────────────────────────────┬─────────────────────────────────┘
                                │ USDC / USDT on Stellar
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FlezPay Backend (Django REST)                │
│  • Payment Intent service (creates unique memo / reference)     │
│  • Horizon / RPC watcher + webhook listener                     │
│  • On-chain verification (asset, amount, destination, memo)     │
│  • Order reconciliation & state machine                         │
│  • Merchant ledger credit (fiat-equivalent)                     │
│  • Settlement orchestrator → Yellow Card                        │
└───────────────┬───────────────────────────────┬─────────────────┘
                │                               │
                ▼                               ▼
┌───────────────────────────┐     ┌──────────────────────────────┐
│   Anchor Platform Layer   │     │      Yellow Card API         │
│  (SEP standards, status,  │     │  (USDC deposit → local fiat  │
│   verification helpers)   │     │   withdrawal for merchant)   │
└───────────────────────────┘     └──────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Merchant FlezPay Dashboard                   │
│  Sees only fiat balance & withdrawal options (bank / mobile     │
│  money). No crypto UI or wallets exposed.                       │
└─────────────────────────────────────────────────────────────────┘
```

- **Anchor Platform**: Standardized SEP layer (SEP-6, SEP-10, SEP-12, SEP-24, SEP-31, SEP-38) for transaction status handling, authentication, and off-ramp interoperability.
- **Stellar Wallets Kit**: Frictionless wallet presentation supporting popular Stellar wallets (Freighter, Albedo, Lobstr).
- **Yellow Card**: Operational on/off-ramp settlement partner converting USDC to local African fiat currencies (NGN, GHS, KES, etc.).

---

## 🚀 Quickstart & Setup

### Prerequisites
- Python 3.11+
- Redis (for Celery background workers and real-time WebSockets)
- Virtual Environment tool (`venv`)

### 1. Clone the Repository
```bash
git clone https://github.com/arepadeperemi/flezpay_dev.git
cd flezpay_dev
```

### 2. Set Up Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env` and configure your credentials:
```bash
cp .env.example .env
```

### 4. Database Setup & Migrations
```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

### 5. Run Development Server
```bash
python manage.py runserver 8000
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## 🔒 Security & Public Validation Note

This repository is published for **public demonstration, architectural review, and product validation**. All live production secrets, service credentials, private keys, customer records, and identity verification files have been deliberately excluded. Please use the provided `.env.example` template to supply your own testnet keys.

---

## 📄 License
This codebase is distributed for product evaluation, architectural review, and partner integration testing. All rights reserved by FlezPay.
