package com.devops.copilot.modules.file.service;

import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.modules.file.config.MinioProperties;
import com.devops.copilot.modules.file.logging.IngestFlowLog;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import io.minio.StatObjectArgs;
import io.minio.StatObjectResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.InputStream;

/**
 * MinIO 封装：流式上传，禁止把整文件读进堆内存。
 */
@Service
public class FileStorageService {

    private static final Logger log = LoggerFactory.getLogger(FileStorageService.class);

    private final MinioClient minioClient;
    private final MinioProperties properties;

    public FileStorageService(MinioClient minioClient, MinioProperties properties) {
        this.minioClient = minioClient;
        this.properties = properties;
    }

    public String bucket() {
        return properties.getBucket();
    }

    public void uploadStream(String objectKey, InputStream in, long size, String contentType) {
        uploadStream(objectKey, in, size, contentType, "file");
    }

    /**
     * @param kind 日志用：knowledge | analysis
     * @param size 已知长度时传入；未知可用 -1，由 SDK 走 multipart
     */
    public void uploadStream(String objectKey, InputStream in, long size, String contentType, String kind) {
        try {
            PutObjectArgs.Builder builder = PutObjectArgs.builder()
                    .bucket(properties.getBucket())
                    .object(objectKey)
                    .stream(in, size, -1);
            if (contentType != null && !contentType.isBlank()) {
                builder.contentType(contentType);
            }
            minioClient.putObject(builder.build());
            log.info(IngestFlowLog.msg(
                    kind,
                    "04.minio_upload",
                    "bucket=" + properties.getBucket()
                            + " objectKey=" + objectKey
                            + " sizeBytes=" + size
                            + " contentType=" + contentType));
        } catch (Exception ex) {
            log.error(IngestFlowLog.msg(
                    kind,
                    "04.minio_fail",
                    "objectKey=" + objectKey + " error=\"" + IngestFlowLog.preview(ex.getMessage()) + "\""));
            throw new BizException(ErrorCode.STORAGE_ERROR, "上传对象存储失败");
        }
    }

    public StatObjectResponse stat(String objectKey) {
        try {
            return minioClient.statObject(
                    StatObjectArgs.builder()
                            .bucket(properties.getBucket())
                            .object(objectKey)
                            .build());
        } catch (Exception ex) {
            throw new BizException(ErrorCode.STORAGE_ERROR, "对象不存在或无法访问");
        }
    }
}
