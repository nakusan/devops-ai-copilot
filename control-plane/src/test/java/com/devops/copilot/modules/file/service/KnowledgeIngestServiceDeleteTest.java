package com.devops.copilot.modules.file.service;

import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.modules.file.domain.entity.KnowledgeDocument;
import com.devops.copilot.modules.file.domain.enums.JobStatus;
import com.devops.copilot.modules.file.kafka.IngestEventProducer;
import com.devops.copilot.modules.file.mapper.IngestJobMapper;
import com.devops.copilot.modules.file.mapper.KnowledgeDocumentMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

/**
 * 知识库文档删除：归属校验、处理中守卫、幂等、MinIO 失败不阻塞。
 */
@ExtendWith(MockitoExtension.class)
class KnowledgeIngestServiceDeleteTest {

    private static final long OWNER_ID = 1L;
    private static final String KIND = "knowledge";
    private static final String OBJECT_KEY = "knowledge/doc/original.md";

    @Mock
    private KnowledgeDocumentMapper documentMapper;
    @Mock
    private IngestJobMapper ingestJobMapper;
    @Mock
    private FileStorageService fileStorageService;
    @Mock
    private UploadPolicyService uploadPolicyService;
    @Mock
    private IngestEventProducer ingestEventProducer;

    @InjectMocks
    private KnowledgeIngestService service;

    private KnowledgeDocument doc(UUID id, Long userId, JobStatus status) {
        KnowledgeDocument d = new KnowledgeDocument();
        d.setId(id);
        d.setUserId(userId);
        d.setStatus(status.name());
        d.setObjectKey(OBJECT_KEY);
        return d;
    }

    @Test
    void deletesRowThenObjectWhenCompleted() {
        UUID id = UUID.randomUUID();
        when(documentMapper.selectById(id)).thenReturn(doc(id, OWNER_ID, JobStatus.COMPLETED));
        when(documentMapper.deleteById(id)).thenReturn(1);

        service.delete(id, OWNER_ID);

        verify(documentMapper).deleteById(id);
        verify(fileStorageService).removeQuietly(OBJECT_KEY, KIND);
        // chunks 与 ingest_jobs 靠 DB 的 ON DELETE CASCADE，服务层不该自己删
        verifyNoInteractions(ingestJobMapper);
    }

    @Test
    void deletesFailedDocumentToo() {
        UUID id = UUID.randomUUID();
        when(documentMapper.selectById(id)).thenReturn(doc(id, OWNER_ID, JobStatus.FAILED));
        when(documentMapper.deleteById(id)).thenReturn(1);

        service.delete(id, OWNER_ID);

        verify(documentMapper).deleteById(id);
    }

    @ParameterizedTest
    @ValueSource(strings = {"PENDING", "PROCESSING"})
    void rejectsWhileInFlight(String status) {
        UUID id = UUID.randomUUID();
        when(documentMapper.selectById(id)).thenReturn(doc(id, OWNER_ID, JobStatus.valueOf(status)));

        BizException ex = assertThrows(BizException.class, () -> service.delete(id, OWNER_ID));

        assertEquals(ErrorCode.CONFLICT, ex.getErrorCode());
        // 关键：行没删、对象没碰，worker 的状态回调仍能正常落地
        verify(documentMapper, never()).deleteById(id);
        verify(fileStorageService, never()).removeQuietly(anyString(), anyString());
    }

    @Test
    void rejectsOtherUsersDocument() {
        UUID id = UUID.randomUUID();
        when(documentMapper.selectById(id)).thenReturn(doc(id, 999L, JobStatus.COMPLETED));

        BizException ex = assertThrows(BizException.class, () -> service.delete(id, OWNER_ID));

        assertEquals(ErrorCode.FORBIDDEN, ex.getErrorCode());
        verify(documentMapper, never()).deleteById(id);
    }

    @Test
    void rejectsMissingDocument() {
        UUID id = UUID.randomUUID();
        when(documentMapper.selectById(id)).thenReturn(null);

        BizException ex = assertThrows(BizException.class, () -> service.delete(id, OWNER_ID));

        assertEquals(ErrorCode.NOT_FOUND, ex.getErrorCode());
    }

    @Test
    void skipsObjectRemovalWhenRowAlreadyGone() {
        UUID id = UUID.randomUUID();
        when(documentMapper.selectById(id)).thenReturn(doc(id, OWNER_ID, JobStatus.COMPLETED));
        // 并发下另一请求已先删掉同一行
        when(documentMapper.deleteById(id)).thenReturn(0);

        service.delete(id, OWNER_ID);

        verify(fileStorageService, never()).removeQuietly(anyString(), anyString());
    }

    @Test
    void succeedsEvenIfObjectRemovalFails() {
        UUID id = UUID.randomUUID();
        when(documentMapper.selectById(id)).thenReturn(doc(id, OWNER_ID, JobStatus.COMPLETED));
        when(documentMapper.deleteById(id)).thenReturn(1);
        when(fileStorageService.removeQuietly(OBJECT_KEY, KIND)).thenReturn(false);

        // MinIO 残留只是存储垃圾，不能把已成功的 DB 删除报成失败
        service.delete(id, OWNER_ID);

        verify(documentMapper).deleteById(id);
    }
}
