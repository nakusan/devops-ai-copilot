package com.devops.copilot.modules.conversation.client;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class AiPlaneClientTest {

    @Test
    void padTraceIdTo32Hex() {
        assertEquals("0000000000000000000000000000000a", AiPlaneClient.padTraceId("a"));
        assertEquals("4bf92f3577b34da6a3ce929d0e0e4736", AiPlaneClient.padTraceId("4bf92f3577b34da6a3ce929d0e0e4736"));
    }
}
