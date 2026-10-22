import Foundation
import Vision

// Uses macOS Vision already present on the system. No network or model download.
do {
    let data = FileHandle.standardInput.readDataToEndOfFile()
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["en-US"]
    request.usesLanguageCorrection = true
    let handler = VNImageRequestHandler(data: data, options: [:])
    try handler.perform([request])
    let lines = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }
    print(lines.joined(separator: "\n"))
} catch {
    FileHandle.standardError.write(Data("Local OCR failed: \(error)".utf8))
    exit(1)
}
