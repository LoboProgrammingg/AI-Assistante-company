import { useState, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { 
  FileText, Upload, Search, Filter, Trash2, Brain, 
  FileIcon, FolderOpen, MoreVertical, X, Check, Download
} from "lucide-react"
import { documentsApi, type Document, type DocumentListResponse } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

const CATEGORIES = [
  { value: "work", label: "Trabalho", color: "bg-blue-500" },
  { value: "personal", label: "Pessoal", color: "bg-green-500" },
  { value: "study", label: "Estudo", color: "bg-purple-500" },
  { value: "finance", label: "Finanças", color: "bg-yellow-500" },
  { value: "health", label: "Saúde", color: "bg-red-500" },
  { value: "legal", label: "Jurídico", color: "bg-gray-500" },
  { value: "other", label: "Outros", color: "bg-slate-500" },
]

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getCategoryInfo(category: string) {
  return CATEGORIES.find(c => c.value === category) || CATEGORIES[6]
}

export function Documents() {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  const [search, setSearch] = useState("")
  const [categoryFilter, setCategoryFilter] = useState<string>("all")
  const [aiFilter, setAiFilter] = useState<string>("all")
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadData, setUploadData] = useState({
    title: "",
    description: "",
    category: "other",
    tags: "",
    send_to_ai: false,
  })

  const { data: documentsData, isLoading } = useQuery({
    queryKey: ["documents", search, categoryFilter, aiFilter],
    queryFn: async () => {
      const params: Record<string, unknown> = { limit: 50 }
      if (search) params.search = search
      if (categoryFilter !== "all") params.category = categoryFilter
      if (aiFilter !== "all") params.send_to_ai = aiFilter === "ai"
      const response = await documentsApi.list(params as Parameters<typeof documentsApi.list>[0])
      return response.data
    },
  })

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile) throw new Error("Nenhum arquivo selecionado")
      return documentsApi.upload(selectedFile, uploadData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] })
      setUploadDialogOpen(false)
      setSelectedFile(null)
      setUploadData({ title: "", description: "", category: "other", tags: "", send_to_ai: false })
    },
  })

  const toggleAiMutation = useMutation({
    mutationFn: (id: number) => documentsApi.toggleAi(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => documentsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] })
    },
  })

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      setUploadData(prev => ({ ...prev, title: file.name.split(".")[0] }))
      setUploadDialogOpen(true)
    }
  }

  const documents = documentsData?.items || []
  const aiCount = documentsData?.ai_count || 0
  const aiLimit = documentsData?.ai_limit || 25

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Documentos</h1>
          <p className="text-muted-foreground">
            {documentsData?.total || 0} documentos cadastrados
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-2 bg-muted rounded-lg">
            <Brain className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">{aiCount}/{aiLimit} para IA</span>
          </div>
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            accept=".pdf,.txt,.doc,.docx,.md,.csv,.json,.xml"
            onChange={handleFileSelect}
          />
          <Button onClick={() => fileInputRef.current?.click()}>
            <Upload className="h-4 w-4 mr-2" />
            Enviar Documento
          </Button>
        </div>
      </div>

      <div className="flex gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar documentos..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={categoryFilter} onValueChange={setCategoryFilter}>
          <SelectTrigger className="w-[180px]">
            <Filter className="h-4 w-4 mr-2" />
            <SelectValue placeholder="Categoria" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas categorias</SelectItem>
            {CATEGORIES.map(cat => (
              <SelectItem key={cat.value} value={cat.value}>{cat.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={aiFilter} onValueChange={setAiFilter}>
          <SelectTrigger className="w-[180px]">
            <Brain className="h-4 w-4 mr-2" />
            <SelectValue placeholder="Status IA" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos</SelectItem>
            <SelectItem value="ai">Enviados para IA</SelectItem>
            <SelectItem value="not_ai">Não enviados</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
      ) : documents.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FolderOpen className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">Nenhum documento encontrado</h3>
            <p className="text-muted-foreground text-center mb-4">
              Envie documentos para organizar e usar como contexto para a IA
            </p>
            <Button onClick={() => fileInputRef.current?.click()}>
              <Upload className="h-4 w-4 mr-2" />
              Enviar primeiro documento
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {documents.map((doc) => {
            const catInfo = getCategoryInfo(doc.category)
            return (
              <Card key={doc.id} className="relative group">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className={cn("p-2 rounded-lg", catInfo.color)}>
                        <FileText className="h-5 w-5 text-white" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <CardTitle className="text-base truncate">
                          {doc.title || doc.original_filename}
                        </CardTitle>
                        <p className="text-xs text-muted-foreground">
                          {formatFileSize(doc.file_size)}
                        </p>
                      </div>
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem 
                          onClick={() => documentsApi.download(doc.id)}
                        >
                          <Download className="h-4 w-4 mr-2" />
                          Baixar
                        </DropdownMenuItem>
                        <DropdownMenuItem 
                          onClick={() => toggleAiMutation.mutate(doc.id)}
                          disabled={!doc.send_to_ai && aiCount >= aiLimit}
                        >
                          <Brain className="h-4 w-4 mr-2" />
                          {doc.send_to_ai ? "Remover da IA" : "Enviar para IA"}
                        </DropdownMenuItem>
                        <DropdownMenuItem 
                          onClick={() => deleteMutation.mutate(doc.id)}
                          className="text-destructive"
                        >
                          <Trash2 className="h-4 w-4 mr-2" />
                          Excluir
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </CardHeader>
                <CardContent>
                  {doc.description && (
                    <p className="text-sm text-muted-foreground line-clamp-2 mb-3">
                      {doc.description}
                    </p>
                  )}
                  <div className="flex items-center justify-between">
                    <Badge variant="secondary" className="text-xs">
                      {catInfo.label}
                    </Badge>
                    {doc.send_to_ai && (
                      <Badge className="bg-primary text-primary-foreground text-xs">
                        <Brain className="h-3 w-3 mr-1" />
                        IA
                      </Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Enviar Documento</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {selectedFile && (
              <div className="flex items-center gap-3 p-3 bg-muted rounded-lg">
                <FileIcon className="h-8 w-8 text-primary" />
                <div>
                  <p className="font-medium">{selectedFile.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {formatFileSize(selectedFile.size)}
                  </p>
                </div>
              </div>
            )}
            <div className="space-y-2">
              <Label>Título</Label>
              <Input
                value={uploadData.title}
                onChange={(e) => setUploadData(prev => ({ ...prev, title: e.target.value }))}
                placeholder="Nome do documento"
              />
            </div>
            <div className="space-y-2">
              <Label>Descrição</Label>
              <Textarea
                value={uploadData.description}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setUploadData(prev => ({ ...prev, description: e.target.value }))}
                placeholder="Descrição opcional"
                rows={2}
              />
            </div>
            <div className="space-y-2">
              <Label>Categoria</Label>
              <Select 
                value={uploadData.category} 
                onValueChange={(v: string) => setUploadData(prev => ({ ...prev, category: v }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map(cat => (
                    <SelectItem key={cat.value} value={cat.value}>{cat.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Tags (separadas por vírgula)</Label>
              <Input
                value={uploadData.tags}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setUploadData(prev => ({ ...prev, tags: e.target.value }))}
                placeholder="tag1, tag2, tag3"
              />
            </div>
            <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
              <div className="flex items-center gap-2">
                <Brain className="h-5 w-5 text-primary" />
                <div>
                  <p className="font-medium text-sm">Enviar para IA</p>
                  <p className="text-xs text-muted-foreground">
                    Usar como contexto nas conversas ({aiCount}/{aiLimit})
                  </p>
                </div>
              </div>
              <Switch
                checked={uploadData.send_to_ai}
                onCheckedChange={(v: boolean) => setUploadData(prev => ({ ...prev, send_to_ai: v }))}
                disabled={aiCount >= aiLimit}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setUploadDialogOpen(false)}>
              Cancelar
            </Button>
            <Button 
              onClick={() => uploadMutation.mutate()}
              disabled={uploadMutation.isPending}
            >
              {uploadMutation.isPending ? "Enviando..." : "Enviar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
