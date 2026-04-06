# Changelog — Bazaar@IITGN Upgrade

## Summary

Upgraded "Campus Trading Application" to fully satisfy the Bazaar@IITGN hackathon problem statement. All 7 implementation phases completed without rewriting the project — only extensions and modifications to existing code.

---

## Files Modified

### `app/models.py`
- **`Member`** — added `hostel`, `wing`, `karma_score` columns; added `watchlist_items`, `reports_made`, `reports_received` relationships
- **`Product`** — added `status` (available/reserved/sold), `tags`, `is_urgent`, `pickup_point` columns; added `watchlist_items`, `reports` relationships
- **`BargainingProposal`** — added `counter_price`, `updated_at` columns; updated status values: `pending / countered / accepted / rejected`
- **New model: `Watchlist`** — member ↔ product bookmark with unique constraint
- **New model: `Report`** — flagging system with `reporter_id`, `reported_id`, `product_id`, `reason`, `details`, `status`

### `app/helpers.py`
- Added `recalculate_karma(member_id)` — calculates avg review rating × 20 and stores to `karma_score`

### `app/routes/auth.py`
- **Domain restriction** — `@iitgn.ac.in` enforced at both register and login with clear error message
- **Registration** — added `hostel` and `wing` fields; `HOSTELS` and `WINGS` lists defined
- No breaking changes to existing session logic

### `app/routes/products.py` (major rewrite/extension)
- **`CATEGORIES`** — added `Cycles` and `Hostel Gear`
- **`marketplace()`** — added hostel filter, tag search, urgent filter, price insights per category, watchlist set injection
- **`add_product()`** — added `tags`, `pickup_point`, `is_urgent` fields
- **`edit_product()`** — new route, reuses `add_product.html` in edit mode
- **`product_detail()`** — added proposal list for seller, counter-offer display for buyer, watchlist status, review gate check, price insights inline
- **`request_buy()`** — now sets `product.status = 'reserved'`
- **`respond_purchase_request()`** — added `SELECT FOR UPDATE` race condition guard; auto-rejects other pending requests; auto-reverts status on rejection
- **`cancel_purchase_request()`** — reverts product status to `available` when no pending requests remain
- **`respond_proposal()`** — added `countered` action with `counter_price`
- **New route: `accept_counter()`** — buyer accepts a counter-offer
- **New route: `toggle_watchlist()`** — add/remove product from watchlist
- **New route: `watchlist()`** — `/watchlist` page
- **New route: `report_product()`** — submit a report on a listing
- **New route: `my_offers()`** — `/my-offers` page showing buyer's all proposals
- **`add_review()`** — gated: requires completed transaction OR approved purchase request; calls `recalculate_karma()` after save

### `app/routes/main.py`
- **`dashboard()`** — added active offers, incoming offers count, watchlist count
- **`edit_profile()`** — added `hostel` and `wing` save
- Imports `HOSTELS`, `WINGS` from `auth.py`

### `app/routes/admin.py`
- **`dashboard()`** — added `open_reports` count
- **New route: `reports()`** — `/admin/reports` with status filter
- **New route: `update_report()`** — mark report as reviewed/dismissed

---

## Files Added

### `migrate.py`
One-time migration script. Uses `ALTER TABLE IF NOT EXISTS` — safe to run on existing database. Adds all new columns and creates `Watchlist` and `Reports` tables.

### `app/templates/watchlist.html`
Watchlist page showing saved items with sold/reserved status overlays.

### `app/templates/my_offers.html`
Buyer's offer history showing all proposals with counter-offer accept buttons inline.

### `app/templates/admin_reports.html`
Admin report management page with status filtering and review/dismiss actions.

---

## Templates Updated

| Template | Changes |
|---|---|
| `base.html` | Renamed to Bazaar@IITGN; added Watchlist nav link |
| `login.html` | Updated branding; added IITGN domain hint |
| `register.html` | Added hostel/wing dropdowns; domain notice |
| `marketplace.html` | Hostel filter, urgent toggle, tag chips, price insights bar, watchlist button per card |
| `add_product.html` | Added tags, pickup_point, is_urgent fields; edit mode support |
| `product_detail.html` | Full offer/counter/review flow; watchlist toggle; status badges; price insight inline; report form; seller purchase request management; karma display |
| `dashboard.html` | Active offers panel; incoming offers alert; watchlist count; karma stat card |
| `profile.html` | Karma circle display; hostel/wing; profile header card redesign |
| `edit_profile.html` | Added hostel/wing dropdowns |
| `admin_dashboard.html` | Open reports stat card; admin nav links |

---

## Features Implemented by Phase

### Phase 1 — Authentication ✅
- `@iitgn.ac.in` domain restriction (register + login)
- Karma score added to Member model and displayed on profile
- Role column existed; `admin` role fully enforced via `admin_required` decorator

### Phase 2 — Listings ✅
- Added Cycles + Hostel Gear categories
- Hostel + Wing filtering in marketplace
- Tag-based search on title / description / tags
- Image upload was already working — reused
- Urgent Sale flag; Preferred pickup point

### Phase 3 — Transaction + Negotiation ✅
- Full Offer → Counter → Accept/Reject flow
- Available → Reserved → Sold status lifecycle
- Race condition prevention with `SELECT FOR UPDATE`
- Auto-reject competing requests on approval
- HTTP polling chat retained (no new library dependency)

### Phase 4 — Reputation System ✅
- `recalculate_karma()` called on every review save
- Reviews gated on transaction completion
- Flag/Report system with admin management panel

### Phase 5 — User Dashboard ✅
- Items I'm Selling — `/my-listings` (existing, enhanced with pending offer counts)
- My Offers — `/my-offers` (new)
- Watchlist — `/watchlist` (new)
- Dashboard shows active/incoming offer counts and watchlist count

### Phase 6 — Bonus Features ✅
- 🔥 Urgent Sale tag (stored on product, shown in marketplace)
- 📊 Price insights (avg/min/max per category, inline price comparison on detail page)
- 🤝 Preferred pickup points (free-text per listing)
- ⚡ Race condition handling (`SELECT FOR UPDATE` in `respond_purchase_request`)

---

## No Breaking Changes
- All existing routes unchanged in URL structure
- Existing DB tables only received `ADD COLUMN IF NOT EXISTS` — no drops
- All existing sessions remain valid
- Aiven MySQL connection config untouched
