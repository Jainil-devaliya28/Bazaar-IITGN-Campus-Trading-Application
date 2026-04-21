# Bazaar@IITGN — The Community Exchange

This repository implements the IITGN Bazaar problem statement as a fully functional peer-to-peer marketplace for the IIT Gandhinagar community.

It is designed to replace scattered WhatsApp groups and email threads with a single campus-grade platform for buying, selling, negotiating, and completing verified trades.

---

## Problem Statement Execution Overview

### 1. User Authentication & Profile Management

- Secure access is enforced using Google OAuth for `@iitgn.ac.in` accounts.
- Users are assigned one of three roles: `buyer`, `seller`, or `admin`.
- The application stores profile details including name, email, hostel, wing, and karma score.
- Karma is calculated from completed transactions and review history.
- Profiles show an active status overview: items listed, active offers, watchlist count, and karma.

### 2. Smart Listings & Location Intelligence

- Users can create listings for Electronics, Books, Cycles, Hostel Gear, and custom categories.
- Each listing supports high-quality image uploads, which are resized and compressed before storage.
- Listings include campus-specific pickup points and hostel/wing metadata so buyers can find local deals.
- Search supports tags, keyword matching, category filters, price range filters, and hostel filters.

### 3. Transaction & Negotiation Layer

- Buyers can submit purchase requests for reserved items.
- The seller can approve, reject, or counter a purchase request.
- A built-in negotiation engine supports offer/counter-offer states.
- When a seller approves a purchase request, the product is reserved and a pending transaction is created.
- The transaction stays pending until both buyer and seller confirm the physical exchange.

### 4. Reputation & Community Safety

- Every completed transaction contributes to the user's karma score.
- Reviews are unlocked only after the transaction is fully completed.
- Admins can moderate users and listings through a dedicated admin panel.
- There is a verified handshake system that prevents a transaction from completing until both parties confirm in-app.

### 5. User Profile Management Features

- Users have a central dashboard showing:
  - Items they are selling
  - Current offers they have made or received
  - Watchlisted items
- Listings can be bookmarked for later review.
- The app supports saving active offers and displaying the status of each negotiation.

---

## Requirements Implemented

### Authentication and Roles

- Google OAuth with strict `@iitgn.ac.in` login validation.
- Session-based login with role propagation.
- Immediate role update support so newly promoted admins receive access without logging out.

### Listings and Location

- Product postings include title, category, price, description, tags, images, and pickup points.
- Hostels and wings are saved to user profiles and used for local filtering.
- Listings show whether an item is available, reserved, or sold.

### Negotiation, Offers, and Transaction Flow

- A purchase request model is used to capture buyer interest.
- Sellers respond with approve, reject, or create a counter offer.
- Accepted requests create a pending transaction record, not a completed sale.
- Both buyer and seller must confirm the deal in the Transactions page.
- The item is marked sold only after verified handshake completion.

### Reputation and Safety

- `karma_score` is updated after successful transactions.
- Completed transactions and product reviews are tied to this reputation system.
- Admin moderation routes allow role management and review of users and reports.

### Accessibility and UX

- Dark mode and high-contrast theme support for inclusive design.
- Keyboard navigation and ARIA labels are added across the interface.
- Offline mode via service worker allows cached pages and fallback content.

---

## Additional Enhancements

### AI and Smart Features

- Automatic tag suggestions based on listing title and description.
- Price-insight widget provides campus-level pricing context for buyers and sellers.
- Urgent sale toggle highlights urgent listings.

### PWA and Offline Support

- Service worker caches key pages, assets, and chat state.
- `offline.html` page displays when network access is unavailable.
- The app manifest enables installable PWA behavior.

### Concurrency and Verification

- Transaction confirmation is handled atomically with database checks.
- Race conditions are prevented when multiple users interact with the same item.
- Preferred pickup points support campus logistics and local meet-up planning.

---

## Implementation Notes

- Backend: Flask + SQLAlchemy with MySQL compatibility.
- Frontend: Jinja2 templates plus progressive enhancement for accessibility and responsiveness.
- Storage: Local `static/uploads/` image storage with compression.
- Real-time behavior: long-polling and session-backed state persistence for chat.

## How to Run

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set environment variables in `.env`.

3. Run migrations if needed:

```bash
python migrate.py
```

4. Start the app:

```bash
flask run
```

---

## Summary

This project implements the IITGN Bazaar problem statement by turning the campus barter problem into a working community marketplace, complete with local discovery, verified transactions, reputation tracking, offline resilience, and an accessible user interface.
