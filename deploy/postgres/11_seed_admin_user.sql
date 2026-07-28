-- 种子：本地联调用管理员（密码 Admin123!）。生产环境请删除或改密。

INSERT INTO users (id, username, password_hash, team_id, role)
VALUES (
    1,
    'admin',
    '$2b$10$vc0BEQcRdErjhUtpEbqCcOb9VX0twgxaHUZ8ELkFwiVlm3b3r0dKi',
    1,
    'ADMIN'
)
ON CONFLICT (username) DO NOTHING;

SELECT setval(pg_get_serial_sequence('users', 'id'), (SELECT COALESCE(MAX(id), 1) FROM users));
