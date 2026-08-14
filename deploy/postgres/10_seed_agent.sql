-- 种子：默认诊断 Agent，便于本地创建 Session 联调（无需先调 Admin API）。

INSERT INTO agents (id, name, model, system_prompt, enable_rag, enable_mcp, rag_top_k, temperature, config_json)
VALUES (
    1,
    '线上故障诊断助手',
    'glm-4.7-flash',
    '你是企业内部 DevOps 故障排查助手。请基于检索到的私有知识与工具结果作答，不确定时明确说明。',
    TRUE,
    TRUE,
    5,
    0.20,
    '{}'::jsonb
)
ON CONFLICT (id) DO NOTHING;

SELECT setval(pg_get_serial_sequence('agents', 'id'), (SELECT MAX(id) FROM agents));
