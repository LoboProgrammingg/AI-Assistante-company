import { useState, useRef, useEffect } from "react"
import { Send, Bot, User, Loader2, Mic, MicOff, Paperclip, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { chatApi, type ChatMessage } from "@/lib/api"
import { cn } from "@/lib/utils"
import toast from "react-hot-toast"

export function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [recordingTime, setRecordingTime] = useState(0)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const recordingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userMessage: ChatMessage = {
      role: "user",
      content: input,
      timestamp: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput("")
    setIsLoading(true)

    try {
      const { data } = await chatApi.sendMessage(input)

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: data.response,
        timestamp: new Date().toISOString(),
        intent: data.intent,
        entities: data.entities,
      }

      setMessages((prev) => [...prev, assistantMessage])

      if (data.next_action?.includes("create")) {
        toast.success("Ação criada com sucesso!")
      }
    } catch (error) {
      toast.error("Erro ao enviar mensagem")
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Desculpe, ocorreu um erro. Tente novamente.",
          timestamp: new Date().toISOString(),
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream)
      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data)
        }
      }

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" })
        const file = new File([audioBlob], `recording_${Date.now()}.webm`, { type: "audio/webm" })
        setAudioFile(file)
        stream.getTracks().forEach((track) => track.stop())
      }

      mediaRecorder.start()
      setIsRecording(true)
      setRecordingTime(0)
      
      recordingIntervalRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1)
      }, 1000)

      toast.success("Gravação iniciada")
    } catch {
      toast.error("Erro ao acessar microfone")
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current)
      }
      toast.success("Gravação finalizada")
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      const validTypes = ["audio/mpeg", "audio/wav", "audio/ogg", "audio/webm", "audio/mp4", "audio/m4a"]
      if (validTypes.includes(file.type) || file.name.match(/\.(mp3|wav|ogg|webm|m4a|opus)$/i)) {
        setAudioFile(file)
        toast.success(`Arquivo selecionado: ${file.name}`)
      } else {
        toast.error("Formato de áudio não suportado")
      }
    }
  }

  const handleSendAudio = async () => {
    if (!audioFile || isLoading) return

    const userMessage: ChatMessage = {
      role: "user",
      content: `🎤 Áudio enviado: ${audioFile.name}`,
      timestamp: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)

    try {
      const { data } = await chatApi.sendAudio(audioFile)

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: data.is_meeting 
          ? `📝 **Reunião processada!**\n\n${data.response}\n\n_Transcrição salva. Acesse a página de Reuniões para ver o resumo completo._`
          : data.response,
        timestamp: new Date().toISOString(),
        intent: data.intent,
        entities: data.entities,
      }

      setMessages((prev) => [...prev, assistantMessage])
      setAudioFile(null)

      if (data.is_meeting) {
        toast.success("Reunião transcrita e resumida!")
      } else if (data.next_action?.includes("create")) {
        toast.success("Ação criada com sucesso!")
      }
    } catch {
      toast.error("Erro ao processar áudio")
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Desculpe, ocorreu um erro ao processar o áudio. Tente novamente.",
          timestamp: new Date().toISOString(),
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const cancelAudio = () => {
    setAudioFile(null)
    toast("Áudio removido")
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col">
      <div className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight">Chat</h1>
        <p className="text-muted-foreground">
          Converse com o assistente para criar lembretes, registrar gastos ou analisar reuniões.
        </p>
      </div>

      <Card className="flex-1 flex flex-col overflow-hidden">
        <CardHeader className="border-b py-4">
          <CardTitle className="text-lg flex items-center gap-2">
            <Bot className="h-5 w-5 text-primary" />
            Assistente IA
          </CardTitle>
        </CardHeader>

        <CardContent className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground">
              <Bot className="h-16 w-16 mb-4 opacity-50" />
              <p className="text-lg font-medium">Olá! Como posso ajudar?</p>
              <p className="text-sm mt-2 max-w-md">
                Experimente: "Me lembre de ligar para o João amanhã às 14h" ou "Gastei 50 reais no almoço"
              </p>
            </div>
          )}

          {messages.map((message, idx) => (
            <div
              key={idx}
              className={cn(
                "flex gap-3",
                message.role === "user" ? "justify-end" : "justify-start"
              )}
            >
              {message.role === "assistant" && (
                <Avatar className="h-8 w-8">
                  <AvatarFallback className="bg-primary text-primary-foreground">
                    <Bot className="h-4 w-4" />
                  </AvatarFallback>
                </Avatar>
              )}

              <div
                className={cn(
                  "max-w-[70%] rounded-lg px-4 py-2",
                  message.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                )}
              >
                <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                {message.intent && (
                  <p className="text-xs mt-1 opacity-70">
                    Intenção: {message.intent}
                  </p>
                )}
              </div>

              {message.role === "user" && (
                <Avatar className="h-8 w-8">
                  <AvatarFallback>
                    <User className="h-4 w-4" />
                  </AvatarFallback>
                </Avatar>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="flex gap-3">
              <Avatar className="h-8 w-8">
                <AvatarFallback className="bg-primary text-primary-foreground">
                  <Bot className="h-4 w-4" />
                </AvatarFallback>
              </Avatar>
              <div className="bg-muted rounded-lg px-4 py-2">
                <Loader2 className="h-4 w-4 animate-spin" />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </CardContent>

        <div className="p-4 border-t">
          {/* Preview do áudio selecionado */}
          {audioFile && (
            <div className="mb-3 p-3 bg-muted rounded-lg flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Mic className="h-4 w-4 text-primary" />
                <span className="text-sm">{audioFile.name}</span>
                <span className="text-xs text-muted-foreground">
                  ({(audioFile.size / 1024).toFixed(1)} KB)
                </span>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" onClick={cancelAudio}>
                  <X className="h-4 w-4" />
                </Button>
                <Button size="sm" onClick={handleSendAudio} disabled={isLoading}>
                  {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                </Button>
              </div>
            </div>
          )}

          {/* Indicador de gravação */}
          {isRecording && (
            <div className="mb-3 p-3 bg-red-100 dark:bg-red-900/30 rounded-lg flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 bg-red-500 rounded-full animate-pulse" />
                <span className="text-sm font-medium">Gravando...</span>
                <span className="text-sm text-muted-foreground">{formatTime(recordingTime)}</span>
              </div>
              <Button size="sm" variant="destructive" onClick={stopRecording}>
                <MicOff className="h-4 w-4 mr-1" /> Parar
              </Button>
            </div>
          )}

          <div className="flex gap-2">
            {/* Input de arquivo oculto */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelect}
              accept="audio/*,.mp3,.wav,.ogg,.webm,.m4a,.opus"
              className="hidden"
            />

            {/* Botão de anexar áudio */}
            <Button
              variant="outline"
              size="icon"
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading || isRecording}
              title="Anexar áudio"
            >
              <Paperclip className="h-4 w-4" />
            </Button>

            {/* Botão de gravar */}
            <Button
              variant={isRecording ? "destructive" : "outline"}
              size="icon"
              onClick={isRecording ? stopRecording : startRecording}
              disabled={isLoading}
              title={isRecording ? "Parar gravação" : "Gravar áudio"}
            >
              {isRecording ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
            </Button>

            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Digite sua mensagem..."
              disabled={isLoading || isRecording}
              className="flex-1"
            />
            <Button onClick={handleSend} disabled={isLoading || !input.trim() || isRecording}>
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
