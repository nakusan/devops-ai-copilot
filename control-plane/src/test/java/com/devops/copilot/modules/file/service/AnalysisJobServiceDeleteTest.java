package com.devops.copilot.modules.file.service;

import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.modules.file.domain.entity.AnalysisJob;
import com.devops.copilot.modules.file.domain.enums.JobStatus;
import com.devops.copilot.modules.file.kafka.IngestEventProducer;
import com.devops.copilot.modules.file.mapper.AnalysisJobMapper;
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
import static org.mockito.Mockito.when;

/**
 * 分析任务删除：源文件与结果 JSON 两个对象都要清，处理中拒绝。
 */
@ExtendWith(MockitoExtension.class)
class AnalysisJobServiceDeleteTest {

    private static final long OWNER_ID = 1L;
    private static final String KIND = "analysis";
    private static final String SOURCE_KEY = "analysis/job/source.log";
    private static final String RESULT_KEY = "analysis/job/result.json";

    @Mock
    private AnalysisJobMapper analysisJobMapper;
    @Mock
    private FileStorageService fileStorageService;
    @Mock
    private UploadPolicyService uploadPolicyService;
    @Mock
    private IngestEventProducer ingestEventProducer;

    @InjectMocks
    private AnalysisJobService service;

    private AnalysisJob job(UUID id, Long userId, JobStatus status, String resultKey) {
        AnalysisJob j = new AnalysisJob();
        j.setId(id);
        j.setUserId(userId);
        j.setStatus(status.name());
        j.setObjectKey(SOURCE_KEY);
        j.setResultObjectKey(resultKey);
        return j;
    }

    @Test
    void removesBothSourceAndResultObjects() {
        UUID id = UUID.randomUUID();
        when(analysisJobMapper.selectById(id))
                .thenReturn(job(id, OWNER_ID, JobStatus.COMPLETED, RESULT_KEY));
        when(analysisJobMapper.deleteById(id)).thenReturn(1);

        service.delete(id, OWNER_ID);

        verify(analysisJobMapper).deleteById(id);
        verify(fileStorageService).removeQuietly(SOURCE_KEY, KIND);
        verify(fileStorageService).removeQuietly(RESULT_KEY, KIND);
    }

    @Test
    void handlesFailedJobWithoutResultObject() {
        UUID id = UUID.randomUUID();
        // 失败任务没跑出 result.json，resultObjectKey 为 null
        when(analysisJobMapper.selectById(id))
                .thenReturn(job(id, OWNER_ID, JobStatus.FAILED, null));
        when(analysisJobMapper.deleteById(id)).thenReturn(1);

        service.delete(id, OWNER_ID);

        verify(fileStorageService).removeQuietly(SOURCE_KEY, KIND);
        verify(fileStorageService).removeQuietly(null, KIND);
    }

    @ParameterizedTest
    @ValueSource(strings = {"PENDING", "PROCESSING"})
    void rejectsWhileInFlight(String status) {
        UUID id = UUID.randomUUID();
        when(analysisJobMapper.selectById(id))
                .thenReturn(job(id, OWNER_ID, JobStatus.valueOf(status), null));

        BizException ex = assertThrows(BizException.class, () -> service.delete(id, OWNER_ID));

        assertEquals(ErrorCode.CONFLICT, ex.getErrorCode());
        verify(analysisJobMapper, never()).deleteById(id);
        verify(fileStorageService, never()).removeQuietly(anyString(), anyString());
    }

    @Test
    void rejectsOtherUsersJob() {
        UUID id = UUID.randomUUID();
        when(analysisJobMapper.selectById(id))
                .thenReturn(job(id, 999L, JobStatus.COMPLETED, RESULT_KEY));

        BizException ex = assertThrows(BizException.class, () -> service.delete(id, OWNER_ID));

        assertEquals(ErrorCode.FORBIDDEN, ex.getErrorCode());
        verify(analysisJobMapper, never()).deleteById(id);
    }

    @Test
    void skipsObjectRemovalWhenRowAlreadyGone() {
        UUID id = UUID.randomUUID();
        when(analysisJobMapper.selectById(id))
                .thenReturn(job(id, OWNER_ID, JobStatus.COMPLETED, RESULT_KEY));
        when(analysisJobMapper.deleteById(id)).thenReturn(0);

        service.delete(id, OWNER_ID);

        verify(fileStorageService, never()).removeQuietly(anyString(), anyString());
    }
}
