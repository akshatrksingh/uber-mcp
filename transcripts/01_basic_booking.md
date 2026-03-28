# Transcript: Basic Booking

**Mode:** mock
**Date:** 2026-03-27

---

**User:** Book me an Uber from NYU to JFK

**Agent:** *`uber_geocode("NYU")` · `uber_geocode("JFK")` · `uber_get_ride_options`*

Here are the available rides from New York University to JFK Airport:

| Option | Price | ETA | Seats |
|--------|-------|-----|-------|
| UberX | $42–$55 | 4 min | 4 |
| Comfort | $55–$70 | 6 min | 4 |
| UberXL | $68–$85 | 8 min | 6 |
| Uber Black | $95–$115 | 10 min | 4 |

Which option would you like?

---

**User:** UberX please

**Agent:** *`uber_request_ride(product_id="mock-uberx-001", confirm=false)`*

Here's your fare preview for UberX:

- **Fare:** $48.00
- **Pickup ETA:** 4 minutes
- **Route:** NYU → JFK Airport

Shall I book this ride? (yes/no)

---

**User:** yes

**Agent:** *`uber_request_ride(product_id="mock-uberx-001", confirm=true)`*

Your ride is confirmed!

- **Driver:** Marcus J. ★ 4.92
- **Vehicle:** Toyota Camry · NYC4821
- **Arriving in:** 4 minutes
- **Ride ID:** mock-ride-3a7f912c

Marcus is on his way to NYU. Have a safe flight!

