1. Flight card should only should **1 uniform price** if the flight is **round-trip** flight, it is showing it twice in the frontend.
2. Flight card's booking url should be uniform when it is ROUND TRIP flight! It is different now. Just use the returned URL from the tool's result. Only show the first url fetched from the API (the outbound flight).
3. The flight should display information like: duration_minutes (e.g. 200mins -> 3hrs 20mins), airplane (e.g. Airbus A330), travel_class (e.g. Economy)
4. The hotel card should also display information like: hotel_class_int, rating, reviews, location_rating, amenities (a expandable list of items), description of the hotel, the image should use image_url fetch from the hotel tool.
5. The attraction card should display information like: description of the attraction returned by the API (default collapsed, expand when user clicks for more info); a link to the wiki page (if any); an embed map when user clicks for the detailed geological info ('location' text in the frontend).
6. Modify the prompt to ask LLM NOT hallucinate ANYTHING about price, including the admission_fee_hkd for the attraction site. ONLY generate the content based on the give information.
7. Modify the prompt to ask LLM try to fill in some 'tips' for the attractions to its best effort. Some general reminders will do. The thumbnail_url should directly use what is fetched from the api if it is provided.
8. You may need to modify the tools in order to get all the information from the API correctly and pass them to LLM correctly with correct structure.
