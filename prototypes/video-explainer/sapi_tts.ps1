param([string]$TextFile, [string]$OutWav, [string]$Voice)
# PROTOTYPE: Windows SAPI (System.Speech) narration. Text is read from a UTF-8 file to avoid console encoding issues.
Add-Type -AssemblyName System.Speech
$text = [System.IO.File]::ReadAllText($TextFile, [System.Text.Encoding]::UTF8)
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice($Voice)
$s.SetOutputToWaveFile($OutWav)
$s.Speak($text)
$s.Dispose()
