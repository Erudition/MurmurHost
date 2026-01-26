import { error } from "winston";
import { Canvas } from "canvas";
import FFMpeg from "fluent-ffmpeg";
import * as ChunkingStreams from "chunking-streams";
import { AudioAnalyzer, audioFreq, height, maxByte, width, chunkSize } from "./audioanalyzer";

/**
 * Visualize an audiofile and return the buffer holding a generated png image.
 * @return Buffer holding the generated png image.
 */
export const visualizeAudioFile = function (filename): Promise<Buffer> {
    return new Promise((resolve, reject) => {
        try {
            const analyzer = new AudioAnalyzer();
            const ffmpeg = FFMpeg(filename);
            const stream = ffmpeg
                .format("u8")
                .audioChannels(1)
                .on("error", (err) => reject(err))
                .audioFrequency(audioFreq)
                .stream(undefined);
            const chunker = new ChunkingStreams.SizeChunker({ chunkSize });
            chunker.on("data", ({ data }) => {
                const arr = new Float32Array(data.length);
                for (let i = 0; i < data.length; i++) {
                    arr[i] = (data[i] / maxByte) * 2 - 1;
                }
                analyzer.analyze(arr);
            });
            chunker.on("end", () => {
                const canvas = new Canvas(width, height);
                analyzer.draw(canvas);
                resolve(canvas.toBuffer());
            });
            stream.pipe(chunker);
        } catch (err) {
            error("Error visualizing audio file:", err);
            reject(err);
        }
    });
};
