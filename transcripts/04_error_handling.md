# Transcript: Error Handling

**Mode:** mock
**Date:** 2026-03-27

---

**User:** Book an Uber from Katz's Deli to Penn Station

**Agent:** *`uber_geocode("Katz's Deli")`*

I found a few possible matches for "Katz's Deli". Could you confirm which one you mean?

1. Katz's Deli, Downtown Manhattan, New York, NY
2. Katz's Deli, Queens, New York, NY
3. Katz's Deli, Brooklyn, New York, NY

---

**User:** The one in Manhattan

**Agent:** *`uber_geocode("Penn Station")`*

Got it — using the Downtown Manhattan location. Now I also found multiple results for "Penn Station":

1. Penn Station, Downtown Manhattan, New York, NY
2. Penn Station, Queens, New York, NY
3. Penn Station, Brooklyn, New York, NY

Penn Station is at 34th St in Midtown Manhattan — did you mean option 1?

---

**User:** Yes, that's right

**Agent:** *`uber_get_ride_options`*

Here are the rides from Katz's Deli (Manhattan) to Penn Station (Manhattan):

| Option | Price | ETA | Seats |
|--------|-------|-----|-------|
| UberX | $42–$55 | 4 min | 4 |
| Comfort | $55–$70 | 6 min | 4 |
| UberXL | $68–$85 | 8 min | 6 |
| Uber Black | $95–$115 | 10 min | 4 |

Which option would you like?

---

**User:** UberX

**Agent:** *`uber_request_ride(product_id="mock-uberx-001", confirm=false)`*

Here's your UberX preview:

- **Fare:** $48.00
- **Pickup ETA:** 4 minutes

Shall I book it?

---

**User:** Actually wait — let me try to book two rides at once

**Agent:** I can only manage one ride at a time. Let's finish booking this one first. Shall I confirm the UberX to Penn Station for $48.00?

---

**User:** Yes

**Agent:** *`uber_request_ride(product_id="mock-uberx-001", confirm=true)`*

Ride confirmed!

- **Driver:** Marcus J. ★ 4.92
- **Vehicle:** Toyota Camry · NYC4821
- **Arriving in:** 4 minutes
- **Ride ID:** mock-ride-9f3a2b17

---

**User:** Book me another Uber to JFK right now

**Agent:** *`uber_geocode("JFK")` · `uber_get_ride_options`*

You already have an active ride in progress (mock-ride-9f3a2b17). I can't book a second ride until that one is completed or cancelled.

Would you like to cancel the current ride and book a new one to JFK instead?

