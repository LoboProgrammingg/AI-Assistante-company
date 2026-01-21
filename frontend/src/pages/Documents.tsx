import { useState, useRef, useCallback } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { 
  FileText, Upload, Search, Filter, Trash2, Brain, 
  FileIcon, FolderOpen, MoreVertical, Download, Grid3X3, List
} from "lucide-react"
import { documentsApi } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { Pagination } from "@/components/ui/pagination"
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

const ITEMS_PER_PAGE = 12

export function Documents() {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  const [search, setSearch] = useState("")
  const [categoryFilter, setCategoryFilter] = useState<string>("all")
  const [aiFilter, setAiFilter] = useState<string>("all")
  const [currentPage, setCurrentPage] = useState(1)
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")
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
    queryKey: ["documents", search, categoryFilter, aiFilter, currentPage],
    queryFn: async () => {
      const params: Record<string, unknown> = { 
        limit: ITEMS_PER_PAGE,
        skip: (currentPage - 1) * ITEMS_PER_PAGE
      }
      if (search) params.search = search
      if (categoryFilter !== "all") params.category = categoryFilter
      if (aiFilter !== "all") params.send_to_ai = aiFilter === "ai"
      const response = await documentsApi.list(params as Parameters<typeof documentsApi.list>[0])
      return response.data
    },
  })

  const handleFilterChange = useCallback((type: "search" | "category" | "ai", value: string) => {
    setCurrentPage(1)
    if (type === "search") setSearch(value)
    else if (type === "category") setCategoryFilter(value)
    else if (type === "ai") setAiFilter(value)
  }, [])

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile) throw new Error("Nenhum arquivo selecionado")
      return documentsApi.upload(selectedFile, uploadData)
    },
    onSuccess: () => {
      // Limpar estado primeiro para evitar re-envios
      setSelectedFile(null)
      setUploadDialogOpen(false)
      setUploadData({ title: "", description: "", category: "other", tags: "", send_to_ai: false })
      // Resetar input file
      if (fileInputRef.current) {
        fileInputRef.current.value = ""
      }
      // Invalidar queries após limpar estado
      queryClient.invalidateQueries({ queryKey: ["documents"] })
    },
    onError: (error) => {
      console.error("Erro no upload:", error)
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
    if (file && !uploadDialogOpen && !uploadMutation.isPending) {
      setSelectedFile(file)
      setUploadData(prev => ({ ...prev, title: file.name.split(".")[0] }))
      setUploadDialogOpen(true)
    }
    // Resetar input para permitir selecionar o mesmo arquivo novamente
    e.target.value = ""
  }

  const documents = documentsData?.items || []
  const aiCount = documentsData?.ai_count || 0
  const aiLimit = documentsData?.ai_limit || 25
  const totalItems = documentsData?.total || 0
  const totalPages = Math.ceil(totalItems / ITEMS_PER_PAGE)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Documentos</h1>
          <p className="text-muted-foreground mt-1">
            {totalItems} documento{totalItems !== 1 ? "s" : ""} • Página {currentPage} de {totalPages || 1}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-4 py-2 bg-primary/10 rounded-full">
            <Brain className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium text-primary">{aiCount}/{aiLimit}</span>
          </div>
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            accept=".pdf,.txt,.doc,.docx,.md,.csv,.json,.xml"
            onChange={handleFileSelect}
          />
          <Button onClick={() => fileInputRef.current?.click()} size="lg">
            <Upload className="h-4 w-4 mr-2" />
            Enviar
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card className="border-0 shadow-sm bg-muted/30">
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-3 items-center">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar documentos..."
                value={search}
                onChange={(e) => handleFilterChange("search", e.target.value)}
                className="pl-10 bg-background border-0 shadow-sm"
              />
            </div>
            <Select value={categoryFilter} onValueChange={(v) => handleFilterChange("category", v)}>
              <SelectTrigger className="w-[160px] bg-background border-0 shadow-sm">
                <Filter className="h-4 w-4 mr-2 text-muted-foreground" />
                <SelectValue placeholder="Categoria" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas</SelectItem>
                {CATEGORIES.map(cat => (
                  <SelectItem key={cat.value} value={cat.value}>{cat.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={aiFilter} onValueChange={(v) => handleFilterChange("ai", v)}>
              <SelectTrigger className="w-[160px] bg-background border-0 shadow-sm">
                <Brain className="h-4 w-4 mr-2 text-muted-foreground" />
                <SelectValue placeholder="Status IA" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="ai">Com IA</SelectItem>
                <SelectItem value="not_ai">Sem IA</SelectItem>
              </SelectContent>
            </Select>
            <div className="flex items-center border rounded-lg bg-background shadow-sm">
              <Button
                variant={viewMode === "grid" ? "secondary" : "ghost"}
                size="icon"
                className="h-9 w-9 rounded-r-none"
                onClick={() => setViewMode("grid")}
              >
                <Grid3X3 className="h-4 w-4" />
              </Button>
              <Button
                variant={viewMode === "list" ? "secondary" : "ghost"}
                size="icon"
                className="h-9 w-9 rounded-l-none"
                onClick={() => setViewMode("list")}
              >
                <List className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

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
        <>
          {viewMode === "grid" ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {documents.map((doc) => {
                const catInfo = getCategoryInfo(doc.category)
                return (
                  <Card key={doc.id} className="group hover:shadow-lg transition-all duration-200 border-0 shadow-sm">
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <div className={cn("p-2.5 rounded-xl", catInfo.color, "shadow-sm")}>
                            <FileText className="h-5 w-5 text-white" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <CardTitle className="text-sm font-semibold truncate">
                              {doc.title || doc.original_filename}
                            </CardTitle>
                            <p className="text-xs text-muted-foreground mt-0.5">
                              {formatFileSize(doc.file_size)}
                            </p>
                          </div>
                        </div>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity">
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => documentsApi.download(doc.id)}>
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
                            <DropdownMenuItem onClick={() => deleteMutation.mutate(doc.id)} className="text-destructive">
                              <Trash2 className="h-4 w-4 mr-2" />
                              Excluir
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </CardHeader>
                    <CardContent className="pt-0">
                      {doc.description && (
                        <p className="text-xs text-muted-foreground line-clamp-2 mb-3">{doc.description}</p>
                      )}
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs font-normal">{catInfo.label}</Badge>
                        {doc.send_to_ai && (
                          <Badge className="bg-primary/10 text-primary text-xs border-0">
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
          ) : (
            <Card className="border-0 shadow-sm overflow-hidden">
              <div className="divide-y">
                {documents.map((doc) => {
                  const catInfo = getCategoryInfo(doc.category)
                  return (
                    <div key={doc.id} className="flex items-center gap-4 p-4 hover:bg-muted/50 transition-colors group">
                      <div className={cn("p-2.5 rounded-xl shrink-0", catInfo.color)}>
                        <FileText className="h-5 w-5 text-white" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{doc.title || doc.original_filename}</p>
                        <p className="text-sm text-muted-foreground truncate">{doc.description || "Sem descrição"}</p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-sm text-muted-foreground">{formatFileSize(doc.file_size)}</span>
                        <Badge variant="outline" className="text-xs">{catInfo.label}</Badge>
                        {doc.send_to_ai && <Badge className="bg-primary/10 text-primary text-xs border-0">IA</Badge>}
                      </div>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => documentsApi.download(doc.id)}>
                            <Download className="h-4 w-4 mr-2" />Baixar
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => toggleAiMutation.mutate(doc.id)} disabled={!doc.send_to_ai && aiCount >= aiLimit}>
                            <Brain className="h-4 w-4 mr-2" />{doc.send_to_ai ? "Remover da IA" : "Enviar para IA"}
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => deleteMutation.mutate(doc.id)} className="text-destructive">
                            <Trash2 className="h-4 w-4 mr-2" />Excluir
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  )
                })}
              </div>
            </Card>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex justify-center pt-4">
              <Pagination
                currentPage={currentPage}
                totalPages={totalPages}
                onPageChange={setCurrentPage}
              />
            </div>
          )}
        </>
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
