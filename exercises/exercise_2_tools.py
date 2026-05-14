"""Bài Tập 2: Thêm Tools và Knowledge Base

Hoàn thành các TODO để thêm tool và knowledge base entry mới.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from common.llm import get_llm

# Knowledge base
LEGAL_KNOWLEDGE = [
    {
        "id": "ucc_breach",
        "keywords": ["breach", "contract", "remedies", "damages", "ucc"],
        "text": (
            "Under the Uniform Commercial Code (UCC) Article 2, remedies for breach of contract "
            "include: (1) expectation damages; (2) consequential damages; (3) specific performance; "
            "(4) cover damages. Statute of limitations is typically 4 years (UCC § 2-725)."
        ),
    },
    {
        "id": "labor_law_vn",
        "keywords": ["lao động", "sa thải", "vi phạm", "hợp đồng lao động", "bồi thường", "thời hiệu"],
        "text": (
            "Theo Bộ luật Lao động Việt Nam 2019: (1) Thời hiệu khởi kiện tranh chấp lao động "
            "cá nhân là 1 năm kể từ ngày phát hiện quyền lợi bị xâm phạm (Điều 192); (2) Người lao động "
            "bị sa thải trái pháp luật được phục hồi工作, trả lương và đóng BHXH trong thời gian không được làm việc; "
            "(3) Bồi thường nếu không phục hồi工作: ít nhất 2 tháng lương theo hợp đồng; "
            "(4) Thời hiệu khiếu nại quyết định kỷ luật lao động là 180 ngày (Điều 192)."
        ),
    },
]


@tool
def search_legal_knowledge(query: str) -> str:
    """Tìm kiếm trong knowledge base pháp lý."""
    query_lower = query.lower()
    for entry in LEGAL_KNOWLEDGE:
        if any(kw in query_lower for kw in entry["keywords"]):
            return f"[{entry['id']}] {entry['text']}"
    return "Không tìm thấy thông tin liên quan."


@tool
def check_statute_of_limitations(case_type: str) -> str:
    """Kiểm tra thời hiệu khởi kiện theo loại vụ việc."""
    statutes = {
        "contract": "Thời hiệu khởi kiện vi phạm hợp đồng: 4 năm (UCC § 2-725) hoặc 6 năm theo pháp luật Việt Nam.",
        "nda": "Thời hiệu khởi kiện vi phạm NDA: 3 năm (DTSA, 18 U.S.C. § 1836).",
        "labor": "Thời hiệu khởi kiện tranh chấp lao động cá nhân: 1 năm kể từ ngày phát hiện (Bộ luật Lao động VN 2019, Điều 192).",
        "trade_secret": "Thời hiệu khởi kiện vi phạm bí mật thương mại: 3 năm kể từ ngày phát hiện (DTSA).",
        "tort": "Thời hiệu khởi kiện bồi thường thiệt hại ngoài hợp đồng: 3 năm (pháp luật Việt Nam).",
        "tax": "Thời hiệu truy thu thuế: 10 năm đối với trường hợp trốn thuế, 5 năm đối với các trường hợp khác.",
    }
    case_lower = case_type.lower()
    for key, value in statutes.items():
        if key in case_lower:
            return value
    return f"Không tìm thấy thời hiệu cho loại vụ việc '{case_type}'. Các loại hỗ trợ: contract, nda, labor, trade_secret, tort, tax."


async def main():
    load_dotenv()
    llm = get_llm()
    
    # TODO: Thêm tool mới vào danh sách
    tools = [search_legal_knowledge, check_statute_of_limitations]
    llm_with_tools = llm.bind_tools(tools)
    
    question = "Thời hiệu khởi kiện vụ vi phạm hợp đồng là bao lâu?"
    
    messages = [
        SystemMessage(content="Bạn là chuyên gia pháp lý. Sử dụng tools để tra cứu thông tin."),
        HumanMessage(content=question),
    ]
    
    print(f"Câu hỏi: {question}\n")
    
    # First LLM call - decide which tools to use
    response = await llm_with_tools.ainvoke(messages)
    messages.append(response)
    
    # Execute tools if requested
    if response.tool_calls:
        for tool_call in response.tool_calls:
            print(f"🔧 Gọi tool: {tool_call['name']}")
            tool_result = None
            
            if tool_call["name"] == "search_legal_knowledge":
                tool_result = search_legal_knowledge.invoke(tool_call["args"])
            elif tool_call["name"] == "check_statute_of_limitations":
                tool_result = check_statute_of_limitations.invoke(tool_call["args"])
            
            if tool_result:
                messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call["id"]))
        
        # Second LLM call - synthesize final answer
        final_response = await llm_with_tools.ainvoke(messages)
        print(f"\n✅ Kết quả:\n{final_response.content}")
    else:
        print(f"\n✅ Kết quả:\n{response.content}")


if __name__ == "__main__":
    asyncio.run(main())
