package com.premalytics.service;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

/**
 * Shared helper for running a child process (the Python prediction CLIs) and
 * capturing its result. stdout is read on the calling thread while stderr is
 * drained on a separate thread, so a full stderr buffer can't deadlock the read.
 */
public final class ProcessRunner {

    private static final long PROCESS_TIMEOUT_SECONDS = 60;

    private ProcessRunner() {
    }

    /** Start the process, capture stdout/stderr concurrently, and wait (with timeout). */
    public static ProcessResult run(ProcessBuilder pb) throws IOException, InterruptedException {
        Process process = pb.start();

        StringBuilder stderr = new StringBuilder();
        Thread stderrReader = new Thread(() -> stderr.append(readStream(process.getErrorStream())));
        stderrReader.start();

        String stdout = readStream(process.getInputStream());

        boolean finished = process.waitFor(PROCESS_TIMEOUT_SECONDS, TimeUnit.SECONDS);
        stderrReader.join();
        if (!finished) {
            process.destroyForcibly();
            throw new RuntimeException("Process timed out after " + PROCESS_TIMEOUT_SECONDS + "s");
        }

        return new ProcessResult(process.exitValue(), stdout, stderr.toString());
    }

    private static String readStream(InputStream in) {
        try (InputStream is = in) {
            return new String(is.readAllBytes(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            return "";
        }
    }

    /** A finished process's exit code and captured streams. */
    public static final class ProcessResult {
        final int exitCode;
        final String stdout;
        final String stderr;

        ProcessResult(int exitCode, String stdout, String stderr) {
            this.exitCode = exitCode;
            this.stdout = stdout;
            this.stderr = stderr;
        }
    }
}
