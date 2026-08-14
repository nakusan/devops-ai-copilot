package com.devops.copilot.modules.file.service;

import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.modules.file.config.MinioProperties;
import com.devops.copilot.modules.file.logging.IngestFlowLog;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import io.minio.RemoveObjectArgs;
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
            // 成功不打日志：objectKey / sizeBytes 由调用方的 05.stored 承载；失败见下方 04.minio_fail
            minioClient.putObject(builder.build());
        } catch (Exception ex) {
            log.error(IngestFlowLog.msg(
                    kind,
                    "04.minio_fail",
                    "objectKey=" + objectKey + " error=\"" + IngestFlowLog.preview(ex.getMessage()) + "\""));
            throw new BizException(ErrorCode.STORAGE_ERROR, "上传对象存储失败");
        }
    }

    /**
     * 删除对象；失败只记 WARN，不抛异常。
     *
     * <p>调用方通常已经删掉 DB 记录，此时抛异常会让用户以为整个删除失败并重试，
     * 而重试也修不了——残留对象只是存储垃圾，可交给 bucket 生命周期规则兜底。
     * 反过来若 DB 行残留，RAG 会继续检索到已删内容，那才是真问题。
     *
     * @param objectKey 允许为 null/空（如分析任务尚无结果文件），此时直接返回 false
     * @return true 表示已从 MinIO 移除
     */
    public boolean removeQuietly(String objectKey, String kind) {
        if (objectKey == null || objectKey.isBlank()) {
            return false;
        }
        try {
            minioClient.removeObject(
                    RemoveObjectArgs.builder()
                            .bucket(properties.getBucket())
                            .object(objectKey)
                            .build());
            return true;
        } catch (Exception ex) {
            log.warn(IngestFlowLog.msg(
                    kind,
                    "20.minio_orphan",
                    "objectKey=" + objectKey + " error=\"" + IngestFlowLog.preview(ex.getMessage()) + "\""));
            return false;
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
