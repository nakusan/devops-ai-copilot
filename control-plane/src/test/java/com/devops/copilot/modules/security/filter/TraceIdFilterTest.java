package com.devops.copilot.modules.security.filter;

import com.devops.copilot.common.trace.TraceIds;
import io.micrometer.tracing.Span;
import io.micrometer.tracing.TraceContext;
import io.micrometer.tracing.Tracer;
import jakarta.servlet.FilterChain;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TraceIdFilterTest {

    @Mock
    private Tracer tracer;
    @Mock
    private Span span;
    @Mock
    private TraceContext context;
    @Mock
    private HttpServletRequest request;
    @Mock
    private HttpServletResponse response;
    @Mock
    private FilterChain chain;

    @AfterEach
    void clearMdc() {
        TraceIds.clear();
    }

    @Test
    void setsHeaderFromCurrentSpan() throws Exception {
        when(tracer.currentSpan()).thenReturn(span);
        when(span.context()).thenReturn(context);
        when(context.traceId()).thenReturn("4bf92f3577b34da6a3ce929d0e0e4736");
        when(context.spanId()).thenReturn("00f067aa0ba902b7");

        TraceIdFilter filter = new TraceIdFilter(tracer);
        filter.doFilterInternal(request, response, chain);

        verify(response).setHeader(eq(TraceIds.HEADER_X_TRACE_ID), eq("4bf92f3577b34da6a3ce929d0e0e4736"));
        verify(chain).doFilter(request, response);
        // finally 已 clear
        assertEquals("", TraceIds.current());
    }

    @Test
    void fallbackWhenNoCurrentSpan() throws Exception {
        when(tracer.currentSpan()).thenReturn(null);

        TraceIdFilter filter = new TraceIdFilter(tracer);
        filter.doFilterInternal(request, response, chain);

        verify(response).setHeader(eq(TraceIds.HEADER_X_TRACE_ID), org.mockito.ArgumentMatchers.argThat(id ->
                id != null && id.length() == 32 && id.matches("[0-9a-f]{32}")));
        verify(chain).doFilter(request, response);
    }

    @Test
    void fallbackTraceIdIs32Hex() {
        String id = TraceIdFilter.fallbackTraceId();
        assertEquals(32, id.length());
        assertTrue(id.matches("[0-9a-f]{32}"));
        assertFalse(id.contains("-"));
    }
}
