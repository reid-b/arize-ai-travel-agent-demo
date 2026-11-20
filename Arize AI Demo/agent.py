import operator
from datetime import datetime
from typing import Annotated, Literal

from dotenv import load_dotenv
from langchain_core.messages import AnyMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict
from tools import tools_by_name, tools


load_dotenv()


model = ChatOpenAI(model="gpt-4o", temperature=0)
model_with_tools = model.bind_tools(tools)


class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]


def system_prompt() -> str:
    today = datetime.now().strftime("%A, %B %d, %Y")
    return (
        "You are Sojourns, a travel assistant that helps people plan trips. "
        f"Today's date is {today}. "
        "Use the search_flights tool for any flight question. It needs 3-letter IATA airport "
        "codes and a date in YYYY-MM-DD format. If the user gives a date without a year, use "
        "the next upcoming occurrence of that date. "
        "search_flights returns JSON with a status field, a data_mode field and a flights list. "
        "Summarize the flights clearly for the user (airline, times, stops, price). If "
        "data_mode is \"test\", say the fares are sandbox data and not real prices. If status is "
        "\"error\", explain the problem briefly and retry with corrected input when possible. "
        "Use the search_car_rentals tool for rental cars. It needs a pickup location (a city or "
        "airport) and pickup and drop-off dates in YYYY-MM-DD format, and returns JSON in the same "
        "style. Summarize a few good options (vendor, car, price per day, total, cancellation). "
        "Mention that booking links may be affiliate links, and note that this tool only searches "
        "and cannot book. If it returns no_results, quote the service's note, then retry once with "
        "the full airport name (for example Lisbon Humberto Delgado Airport) before giving up. "
        "Check resolved_pickup to see where the service actually searched. Never claim a "
        "reason the tool did not give. "
        "Use the compare_destinations tool when the user wants to compare places, asks which "
        "destination is cheaper, whether a fare is a good deal, the cheapest time to go, or "
        "somewhere similar to a city (for example like Amsterdam but cheaper). It takes an origin "
        "IATA code and 1 to 4 destinations and returns JSON: per-destination fares on several "
        "dates, a baseline price, deals (dates well below baseline), a ranking, and similar "
        "destinations with how much cheaper they are. Present it as a short comparison: typical "
        "price, cheapest date, any deals with percent below baseline, then the similar-city "
        "alternatives and the shared traits. If data_mode is \"test\", say deals are illustrative "
        "sandbox data. Never describe the baseline as official historical fares; it comes from "
        "sampled dates and earlier saved searches. "
        "Use the web_search tool only for general travel information, never for fares, "
        "and if it returns status \"error\" or \"no_results\", say plainly that the search "
        "failed or found nothing, then answer from general knowledge and label it as such. "
        "flight availability or rental prices. "
        "If a tool returns an error, explain it plainly and correct the input if you can."
    )


def llm_call(state: MessagesState) -> dict:
    """Call the LLM with the current messages and available tools."""
    return {
        "messages": [
            model_with_tools.invoke(
                [SystemMessage(content=system_prompt())] + state["messages"]
            )
        ]
    }


def tool_node(state: MessagesState) -> dict:
    """Execute tool calls from the last message."""
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        try:
            observation = tool.invoke(tool_call["args"])
        except Exception as e:  # return the error to the model instead of crashing the request
            observation = f"Tool error ({tool_call['name']}): {type(e).__name__}: {e}"
            print(f"[sojourns] tool error in {tool_call['name']}: {type(e).__name__}: {e}", flush=True)
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}


def should_continue(state: MessagesState) -> Literal["tool_node", "__end__"]:
    """Determine whether to continue to tool execution or end."""
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tool_node"
    return END


def build_agent():
    graph_builder = StateGraph(MessagesState)

    graph_builder.add_node("llm_call", llm_call)
    graph_builder.add_node("tool_node", tool_node)

    graph_builder.add_edge(START, "llm_call")
    graph_builder.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
    graph_builder.add_edge("tool_node", "llm_call")

    agent = graph_builder.compile()
    return agent