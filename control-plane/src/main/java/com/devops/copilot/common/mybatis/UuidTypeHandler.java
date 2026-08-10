package com.devops.copilot.common.mybatis;

import org.apache.ibatis.type.BaseTypeHandler;
import org.apache.ibatis.type.JdbcType;
import org.apache.ibatis.type.MappedJdbcTypes;
import org.apache.ibatis.type.MappedTypes;

import java.sql.CallableStatement;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Types;
import java.util.UUID;

/**
 * PostgreSQL {@code UUID} ↔ {@link java.util.UUID} 的 MyBatis TypeHandler。
 *
 * <p>为何需要：实体在 {@code autoResultMap = true}（如 JSONB + JsonbTypeHandler）时，
 * MyBatis-Plus 会为全部字段构建 ResultMap；若 {@code UUID} 未注册 TypeHandler，
 * 启动期即抛 {@code No typehandler found for property id}，应用无法起来。
 *
 * <p>写法说明：写库用 {@link Types#OTHER} + {@code setObject}，兼容 PG 原生 UUID 列；
 * 读库兼容 driver 返回 {@link UUID} 或字符串两种形态。
 */
@MappedTypes(UUID.class)
@MappedJdbcTypes(JdbcType.OTHER)
public class UuidTypeHandler extends BaseTypeHandler<UUID> {

    @Override
    public void setNonNullParameter(PreparedStatement ps, int i, UUID parameter, JdbcType jdbcType)
            throws SQLException {
        ps.setObject(i, parameter, Types.OTHER);
    }

    @Override
    public UUID getNullableResult(ResultSet rs, String columnName) throws SQLException {
        return toUuid(rs.getObject(columnName));
    }

    @Override
    public UUID getNullableResult(ResultSet rs, int columnIndex) throws SQLException {
        return toUuid(rs.getObject(columnIndex));
    }

    @Override
    public UUID getNullableResult(CallableStatement cs, int columnIndex) throws SQLException {
        return toUuid(cs.getObject(columnIndex));
    }

    private static UUID toUuid(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof UUID uuid) {
            return uuid;
        }
        return UUID.fromString(value.toString());
    }
}
