from typing import TypedDict

from langgraph.graph import END, StateGraph

from nlti.matching import score_match
from nlti.models import Contractor, Tender


class MatchState(TypedDict, total=False):
    contractor: Contractor
    tenders: list[Tender]
    results: list[dict]


def run_matching(state: MatchState) -> dict:
    contractor = state["contractor"]
    results = []
    for tender in state.get("tenders", []):
        result = score_match(contractor, tender)
        results.append({
            "tender_id": tender.id,
            "tender_title": tender.title,
            **result,
        })
    results.sort(key=lambda item: item["score"], reverse=True)
    return {"results": results}


def build_matching_graph():
    graph = StateGraph(MatchState)
    graph.add_node("match_opportunities", run_matching)
    graph.set_entry_point("match_opportunities")
    graph.add_edge("match_opportunities", END)
    return graph.compile()


matching_graph = build_matching_graph()
