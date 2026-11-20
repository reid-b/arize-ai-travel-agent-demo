"""The agent's tools. Add a tool by writing a module here and listing it below."""

from .cars import search_car_rentals
from .destinations import compare_destinations
from .flights import search_flights
from .web import web_search

tools = [web_search, search_flights, search_car_rentals, compare_destinations]

tools_by_name = {t.name: t for t in tools}
