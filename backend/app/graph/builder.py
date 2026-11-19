r"""
START -> extractor -> generator -> validator --(failures & retries left)--> generator
                                            \--(ok or exhausted)--> delegator
delegator -> [interrupt_after: manager review, state saved to Postgres] -> distributor -> END
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph import nodes
from app.graph.state import PipelineState
from app.llm.base import LLMClient

NODE_ORDER = ["extractor", "generator", "validator", "delegator", "distributor"]


def build_graph(llm: LLMClient, checkpointer, max_retries: int = 3) -> CompiledStateGraph:
    async def extractor(state: PipelineState) -> dict:
        return await nodes.extractor(state, llm=llm)

    async def generator(state: PipelineState) -> dict:
        return await nodes.generator(state, llm=llm)

    def route(state: PipelineState) -> str:
        return nodes.route_after_validation(state, max_retries)

    g = StateGraph(PipelineState)
    g.add_node("extractor", extractor)
    g.add_node("generator", generator)
    g.add_node("validator", nodes.validator)
    g.add_node("delegator", nodes.delegator)
    g.add_node("distributor", nodes.distributor)

    g.add_edge(START, "extractor")
    g.add_edge("extractor", "generator")
    g.add_edge("generator", "validator")
    g.add_conditional_edges("validator", route, {"generator": "generator", "delegator": "delegator"})
    g.add_edge("delegator", "distributor")
    g.add_edge("distributor", END)

    return g.compile(checkpointer=checkpointer, interrupt_after=["delegator"])
