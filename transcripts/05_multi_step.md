# Transcript: Multi-Step Flow

**Mode:** mock
**Date:** 2026-03-27

---

**User:** Book me an Uber from Columbia University to Central Park

**Agent:** *`uber_geocode("Columbia University")` · `uber_geocode("Central Park")` · `uber_get_ride_options`*

Here are your ride options from Columbia University to Central Park:

| Option | Price | ETA | Seats |
|--------|-------|-----|-------|
| UberX | $42–$55 | 4 min | 4 |
| Comfort | $55–$70 | 6 min | 4 |
| UberXL | $68–$85 | 8 min | 6 |
| Uber Black | $95–$115 | 10 min | 4 |

Which option would you like?

---

**User:** Actually, can we change the destination to Grand Central instead? There are 5 of us.

**Agent:** *`uber_geocode("Grand Central")` · `uber_get_ride_options`*

No problem! Since you're a group of 5, here are the rides from Columbia University to Grand Central Terminal:

| Option | Price | ETA | Seats |
|--------|-------|-----|-------|
| UberX | $42–$55 | 4 min | 4 — **not enough seats** |
| Comfort | $55–$70 | 6 min | 4 — **not enough seats** |
| UberXL | $68–$85 | 8 min | 6 ✓ |
| Uber Black | $95–$115 | 10 min | 4 — **not enough seats** |

UberXL is your only option that fits 5 people. Want to go with that?

---

**User:** Yes, UberXL

**Agent:** *`uber_request_ride(product_id="mock-uberxl-003", confirm=false)`*

Here's your UberXL preview:

- **Fare:** $75.00
- **Pickup ETA:** 8 minutes
- **Route:** Columbia University → Grand Central Terminal
- **Seats:** 6

Shall I book it for all 5 of you? (yes/no)

---

**User:** Yes, confirmed

**Agent:** *`uber_request_ride(product_id="mock-uberxl-003", confirm=true)`*

Your UberXL is booked!

- **Driver:** Marcus J. ★ 4.92
- **Vehicle:** Toyota Camry · NYC4821
- **Arriving in:** 8 minutes
- **Ride ID:** mock-ride-7e21bc94

Marcus will meet you at Columbia University. There are 6 seats so everyone will be comfortable.

---

**User:** What's the status of our ride?

**Agent:** *`uber_get_ride_status`*

Your driver has accepted the ride and is on the way:

- **Status:** Accepted
- **Driver:** Marcus J. ★ 4.92
- **Vehicle:** Toyota Camry · NYC4821
- **ETA to pickup:** 3 minutes

You should see the car arriving at Columbia shortly!

---

**User:** Never mind, we found another way. Cancel it.

**Agent:** *`uber_cancel_ride(ride_id="mock-ride-7e21bc94")`*

Ride cancelled. No cancellation fee was charged.

Note: If the driver had been very close to pickup, a fee might apply in a real scenario. In this case you're all clear.

