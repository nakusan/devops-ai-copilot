package com.devops.copilot.modules.security.domain;

import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;

import java.util.Collection;
import java.util.List;

/**
 * 认证主体：进入业务层后只依赖本对象，不再重复查库拿 role/teamId。
 *
 * <p>implements UserDetails 是为了塞进 Spring SecurityContext 的标准契约。
 */
public class UserPrincipal implements UserDetails {

    private final Long userId;
    private final String username;
    private final Long teamId;
    private final Role role;

    public UserPrincipal(Long userId, String username, Long teamId, Role role) {
        this.userId = userId;
        this.username = username;
        this.teamId = teamId;
        this.role = role;
    }

    public static UserPrincipal from(User user) {
        return new UserPrincipal(user.getId(), user.getUsername(), user.getTeamId(), user.roleEnum());
    }

    public Long getUserId() {
        return userId;
    }

    public Long getTeamId() {
        return teamId;
    }

    public Role getRole() {
        return role;
    }

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() {
        // hasRole('ADMIN') 会查找 ROLE_ADMIN
        return List.of(new SimpleGrantedAuthority("ROLE_" + role.name()));
    }

    @Override
    public String getPassword() {
        return "";
    }

    @Override
    public String getUsername() {
        return username;
    }

    @Override
    public boolean isAccountNonExpired() {
        return true;
    }

    @Override
    public boolean isAccountNonLocked() {
        return true;
    }

    @Override
    public boolean isCredentialsNonExpired() {
        return true;
    }

    @Override
    public boolean isEnabled() {
        return true;
    }
}
