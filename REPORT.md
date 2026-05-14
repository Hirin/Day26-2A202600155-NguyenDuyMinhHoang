# Báo Cáo Thực Hành - Multi-Agent System với A2A Protocol

**Họ và tên:** Nguyễn Duy Minh Hoàng  
**Mã sinh viên:** 2A202600155  
**Ngày thực hành:** 14/05/2026  
**Môn học:** AI Thực Chiến - Day 26

---

## 1. Tổng Quan Dự Án

Dự án xây dựng hệ thống tư vấn pháp lý multi-agent sử dụng **A2A Protocol** (Google), **LangGraph** và **LangChain**. Hệ thống gồm 5 services chạy phân tán trên 5 port khác nhau, giao tiếp qua A2A protocol với dynamic service discovery.

### Kiến Trúc Hệ Thống

```
                     ┌─────────────────────┐
                     │  Registry Service   │  :10000
                     │  /register /discover│
                     └─────────┬───────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
 Tax Agent :10102    Law Agent :10101    Compliance Agent :10103
        │                      │                      │
        └──────────► delegates in parallel ◄──────────┘
                               │
                        Customer Agent :10100
                               │
                             User
```

---

## 2. Kết Quả Chạy Thực Tế - 5 Stages

### Stage 1: Direct LLM Calling

**Mô tả:** Gọi LLM trực tiếp, không có tools, không có RAG, chỉ dựa vào training data.

**Câu hỏi:** "What are the legal consequences if a company breaches a non-disclosure agreement?"

**Kết quả:** LLM trả lời đầy đủ về 7 loại hậu quả pháp lý khi vi phạm NDA: compensatory damages, injunctive relief, consequential damages, punitive damages, attorney's fees, criminal penalties, reputational harm.

**Nhận xét:**
- LLM phản hồi trong ~10 giây, câu trả lời có cấu trúc rõ ràng.
- Tuy nhiên, câu trả lời mang tính tổng quát, không trích dẫn cụ thể điều luật (UCC, DTSA section).
- Stateless - không nhớ context giữa các lần gọi.

---

### Stage 2: LLM + RAG / Tools

**Mô tả:** Thêm knowledge base (RAG) và tools (search_legal_database, calculate_damages). LLM tự quyết định gọi tool nào.

**Câu hỏi:** Cùng câu hỏi về NDA breach.

**Kết quả:** LLM đã gọi tool `search_legal_database` với query phù hợp, nhận được kết quả trích dẫn cụ thể từ DTSA (18 U.S.C. § 1836), UCC Article 2. Câu trả lời cuối cùng có grounding vào dữ liệu thực.

**Nhận xét:**
- Cải thiện rõ rệt so với Stage 1: câu trả lời trích dẫn cụ thể điều luật, statute.
- LLM biết tự chọn tool phù hợp (search thay vì calculate cho câu hỏi này).
- Hạn chế: chỉ có 1 vòng tool call (single pass), orchestration vẫn thủ công.

---

### Stage 3: Single Agent (ReAct Loop)

**Mô tả:** Agent tự chủ với vòng lặp Think → Act → Observe. Agent tự quyết định gọi tool nào, khi nào dừng.

**Câu hỏi:** Câu hỏi phức tạp - startup $5M revenue vi phạm privacy + trốn thuế.

**Kết quả:** Agent thực hiện **4 bước reasoning**:
1. Gọi `search_legal_database` 2 lần (privacy + tax)
2. Gọi `check_compliance_requirements` (industry analysis)
3. Gọi `calculate_penalty` 2 lần (privacy + tax)
4. Tổng hợp thành báo cáo chi tiết với bảng tóm tắt

**Nhận xét:**
- Agent tự chủ hoàn toàn - tự chia nhỏ vấn đề, tự gọi tools nhiều lần.
- Output rất chi tiết (~500 từ), có bảng so sánh financial risk vs non-financial risk.
- Hạn chế: 1 agent xử lý tất cả domains, tool calls tuần tự (không song song).
- Có deprecation warning về `create_react_agent` (sẽ chuyển sang `langchain.agents`).

---

### Stage 4: Multi-Agent (In-Process)

**Mô tả:** Nhiều agents chuyên biệt chạy song song trong cùng process. Sử dụng LangGraph StateGraph + Send API.

**Câu hỏi:** "If a company breaks a contract and avoids taxes, what are the legal and regulatory consequences?"

**Kết quả:** 4 nodes chạy theo graph:
- `analyze_law` → phân tích pháp lý (993 chars)
- `check_routing` → quyết định routing: needs_tax=True, needs_compliance=True
- `call_tax_specialist` + `call_compliance_specialist` → chạy **song song** (1552 + 1108 chars)
- `aggregate` → tổng hợp (2605 chars)

**Nhận xét:**
- Tax và Compliance agents chạy **song song** (Send API) - cải thiện tốc độ đáng kể.
- Mỗi agent có domain expertise riêng → phân tích chuyên sâu hơn.
- Routing thông minh: LLM quyết định agents nào cần thiết dựa trên câu hỏi.
- Có deprecation warnings về `Send` import và `create_react_agent`.

---

### Stage 5: Distributed A2A (Hệ Thống Phân Tán)

**Mô tả:** Mỗi agent là HTTP service độc lập, giao tiếp qua A2A protocol. Dynamic discovery qua Registry.

**5 services khởi động thành công:**
| Service | Port | Trạng thái |
|---|---|---|
| Registry | 10000 | Running |
| Customer Agent | 10100 | Running |
| Law Agent | 10101 | Running |
| Tax Agent | 10102 | Running |
| Compliance Agent | 10103 | Running |

**Request Flow (trace_id: a6398b1b...):**
```
1. User → Customer Agent (depth=0)
   - CustomerAgent executing | trace=a6398b1b | depth=0
   - LLM quyết định delegate → Law Agent
   
2. Customer Agent → Registry (discover "legal_question")
   - GET /discover/legal_question → Law Agent :10101
   
3. Customer Agent → Law Agent (depth=1) [A2A protocol]
   - LawAgent executing | trace=a6398b1b | depth=1
   - Phân tích pháp lý + Routing: needs_tax=True
   
4. Law Agent → Registry (discover "tax_question")
   - GET /discover/tax_question → Tax Agent :10102
   
5. Law Agent → Tax Agent (depth=2) [A2A protocol]
   - TaxAgent executing | trace=a6398b1b | depth=2
   - Trả về 9931 chars phân tích thuế
   
6. Law Agent → aggregate → trả về Customer Agent
7. Customer Agent → trả về User
```

**Nhận xét:**
- Hệ thống phân tán hoạt động hoàn chỉnh: 5 services độc lập, giao tiếp qua HTTP + A2A.
- **Trace propagation:** `trace_id` và `context_id` truyền xuyên suốt qua 3 hops (depth 0→1→2).
- **Depth guard:** MAX_DELEGATION_DEPTH=3 ngăn vòng lặp vô hạn.
- **Dynamic discovery:** Agents tìm nhau qua Registry, không hardcode URLs.
- Hạn chế: Tổng thời gian xử lý khá lâu (~131 giây) do nhiều LLM calls tuần tự qua network.

---

## 3. Bài Tập Thực Hành

### Exercise 2: Thêm Tools & Knowledge Base

**File:** `exercises/exercise_2_tools.py`

**Đã hoàn thành:**
1. Thêm entry luật lao động Việt Nam vào `LEGAL_KNOWLEDGE` (Bộ luật Lao động 2019, Điều 192)
2. Tạo tool `check_statute_of_limitations` - kiểm tra thời hiệu khởi kiện cho 6 loại vụ việc (contract, nda, labor, trade_secret, tort, tax)
3. Bind tool vào tools list + xử lý tool call trong main loop

**Kết quả test:** Tools được gọi thành công (`search_legal_knowledge` + `check_statute_of_limitations`).

---

### Exercise 4: Thêm Privacy Agent vào Multi-Agent System

**File:** `exercises/exercise_4_multiagent.py`

**Đã hoàn thành:**
1. Implement `privacy_agent` - chuyên gia GDPR, CCPA, data protection, privacy rights
2. Thêm routing logic: kiểm tra keywords "data", "privacy", "gdpr", "dữ liệu", "rò rỉ", "bảo mật"
3. Thêm `privacy_agent` node vào StateGraph + edge đến `aggregate_results`
4. Thêm section privacy analysis vào aggregate output
5. **Fix bug gốc:** Chuyển `check_routing` từ node sang conditional edge function (pattern đúng LangGraph - nodes trả về dict, routing functions trả về Send)

**Kết quả test:** Graph chạy thành công, privacy_agent + tax_agent được gọi song song.

---

## 4. Tổng Hợp So Sánh 5 Stages

| Tiêu chí | Stage 1 | Stage 2 | Stage 3 | Stage 4 | Stage 5 |
|---|---|---|---|---|---|
| **Tools** | Không | Có (2) | Có (3) | Có (2+2) | Có (qua agents) |
| **RAG** | Không | Có | Có | Có | Có |
| **Tự chủ** | Không | Không | Có (ReAct) | Có (graph) | Có (A2A) |
| **Song song** | Không | Không | Không | Có (Send) | Có (distributed) |
| **Scale** | N/A | N/A | N/A | 1 process | N services |
| **Complexity** | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Thời gian phản hồi** | 10.2s | 11.2s | 28.4s | 46.7s | 131.4s |

---

## 5. Đánh Giá Tổng Quan

### Điểm mạnh của hệ thống
- **Kiến trúc rõ ràng:** Progressive learning từ đơn giản đến phức tạp (Stage 1-5).
- **Dynamic discovery:** Agents tự đăng ký và tìm nhau qua Registry, không cần hardcode.
- **Parallel execution:** LangGraph Send API cho phép chạy nhiều agents song song.
- **Trace propagation:** trace_id/context_id truyền xuyên suốt, hỗ trợ debug tốt.
- **Depth guard:** Ngăn chặn vòng lặp delegation vô hạn.

### Điểm cần cải thiện
- **Thời gian phản hồi:** Stage 5 mất ~131 giây (2m11s) do nhiều LLM calls tuần tự qua network. Có thể tối ưu bằng cách gọi Tax + Compliance thật sự song song (hiện tại routing quyết định tuần tự).
- **Model stability:** Một số lần chạy, model trả về output không mạch lạc (garbled text), đặc biệt khi input quá dài.
- **Deprecation warnings:** `create_react_agent` và `Send` import cần update theo LangGraph V1.0+.
- **Error handling:** Thiếu retry logic khi agent fail, chưa có circuit breaker.
- **Compliance Agent ít được gọi:** Trong test, routing chỉ chọn Tax Agent (needs_compliance=False) dù câu hỏi liên quan cả regulatory.

### Bài học rút ra
1. Multi-agent system phù hợp cho các bài toán cần expertise đa lĩnh vực.
2. A2A protocol cho phép tách biệt agents thành services độc lập, dễ scale và maintain.
3. LangGraph cung cấp abstraction tốt cho graph-based agent workflows.
4. Dynamic discovery qua Registry linh hoạt hơn hardcode URLs đáng kể.
5. Trade-off chính giữa complexity và performance: hệ thống phân tán mạnh mẽ nhưng chậm hơn in-process.

---

## 6. Công Nghệ Sử Dụng

| Layer | Công nghệ |
|---|---|
| Agent Framework | LangGraph 1.2.0 |
| LLM Model | deepseek/deepseek-v4-flash:free (qua OpenRouter) |
| A2A Transport | a2a-sdk 0.3.26 |
| Registry | FastAPI + Uvicorn |
| Package Manager | uv 0.9.9 |
| Python | 3.13.9 (venv) |