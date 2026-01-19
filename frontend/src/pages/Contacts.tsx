import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, Search, Trash2, Edit2, Users, Phone, X } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { contactsApi, type Contact, type ContactCreate, type ContactGroupSummary } from "@/lib/api"

const GROUP_COLORS = [
  "bg-pink-500",
  "bg-blue-500",
  "bg-green-500",
  "bg-purple-500",
  "bg-orange-500",
  "bg-cyan-500",
  "bg-yellow-500",
  "bg-red-500",
  "bg-indigo-500",
  "bg-teal-500",
]

const getGroupColor = (groupName: string, index: number = 0): string => {
  const hash = groupName.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0)
  return GROUP_COLORS[(hash + index) % GROUP_COLORS.length]
}

const formatGroupName = (name: string): string => {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

export function Contacts() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState("")
  const [selectedGroup, setSelectedGroup] = useState<string>("")
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingContact, setEditingContact] = useState<Contact | null>(null)

  const { data: contacts, isLoading } = useQuery({
    queryKey: ["contacts", selectedGroup, search],
    queryFn: () =>
      contactsApi
        .list({ group: selectedGroup || undefined, search: search || undefined, limit: 100 })
        .then((r) => r.data),
  })

  const { data: groupsSummary } = useQuery({
    queryKey: ["contacts-groups"],
    queryFn: () => contactsApi.getGroupsSummary().then((r) => r.data),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => contactsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] })
      queryClient.invalidateQueries({ queryKey: ["contacts-groups"] })
    },
  })

  const totalContacts = groupsSummary?.reduce((acc, g) => acc + g.count, 0) ?? 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Contatos</h1>
          <p className="text-muted-foreground">{totalContacts} contatos cadastrados</p>
        </div>
        <Button onClick={() => { setEditingContact(null); setIsModalOpen(true) }}>
          <Plus className="h-4 w-4 mr-2" /> Novo Contato
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
        {groupsSummary?.map((group, index) => (
          <Card
            key={group.group_name}
            className={`cursor-pointer transition-all ${selectedGroup === group.group_name ? "ring-2 ring-primary" : ""}`}
            onClick={() => setSelectedGroup(selectedGroup === group.group_name ? "" : group.group_name)}
          >
            <CardContent className="p-4 flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${getGroupColor(group.group_name, index)}`} />
              <div>
                <p className="text-sm font-medium">{formatGroupName(group.group_name)}</p>
                <p className="text-xs text-muted-foreground">{group.count}</p>
              </div>
            </CardContent>
          </Card>
        ))}
        {(!groupsSummary || groupsSummary.length === 0) && (
          <p className="text-muted-foreground col-span-full text-center py-4">Nenhum grupo criado</p>
        )}
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-4">
          <CardTitle className="text-lg flex items-center gap-2">
            <Users className="h-5 w-5" />
            {selectedGroup ? formatGroupName(selectedGroup) : "Todos os Contatos"}
          </CardTitle>
          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Buscar contato..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8 text-muted-foreground">Carregando...</div>
          ) : contacts?.items?.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">Nenhum contato encontrado</div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {contacts?.items?.map((contact) => (
                <div
                  key={contact.id}
                  className="flex items-center justify-between p-4 rounded-lg bg-muted/50 group"
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-full ${getGroupColor(contact.group_name)} flex items-center justify-center text-white font-medium`}>
                      {contact.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <p className="font-medium">{contact.name}</p>
                      <p className="text-sm text-muted-foreground flex items-center gap-1">
                        <Phone className="h-3 w-3" /> {contact.phone_number}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => { setEditingContact(contact); setIsModalOpen(true) }}
                      className="p-1.5 hover:bg-primary/10 rounded"
                    >
                      <Edit2 className="h-4 w-4 text-primary" />
                    </button>
                    <button
                      onClick={() => confirm(`Deletar ${contact.name}?`) && deleteMutation.mutate(contact.id)}
                      className="p-1.5 hover:bg-destructive/10 rounded"
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {isModalOpen && (
        <ContactModal
          contact={editingContact}
          onClose={() => setIsModalOpen(false)}
          onSuccess={() => {
            setIsModalOpen(false)
            queryClient.invalidateQueries({ queryKey: ["contacts"] })
            queryClient.invalidateQueries({ queryKey: ["contacts-groups"] })
          }}
        />
      )}
    </div>
  )
}

function ContactModal({
  contact,
  onClose,
  onSuccess,
}: {
  contact: Contact | null
  onClose: () => void
  onSuccess: () => void
}) {
  const [form, setForm] = useState<ContactCreate>({
    name: contact?.name ?? "",
    phone_number: contact?.phone_number ?? "",
    group_name: contact?.group_name ?? "outros",
    notes: contact?.notes ?? "",
  })
  const [error, setError] = useState("")

  const createMutation = useMutation({
    mutationFn: (data: ContactCreate) => contactsApi.create(data),
    onSuccess,
    onError: () => setError("Erro ao criar contato"),
  })

  const updateMutation = useMutation({
    mutationFn: (data: ContactCreate) => contactsApi.update(contact!.id, data),
    onSuccess,
    onError: () => setError("Erro ao atualizar contato"),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim() || !form.phone_number.trim()) {
      setError("Nome e telefone são obrigatórios")
      return
    }
    contact ? updateMutation.mutate(form) : createMutation.mutate(form)
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background rounded-lg p-6 w-full max-w-md shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">{contact ? "Editar Contato" : "Novo Contato"}</h2>
          <button onClick={onClose} className="p-1 hover:bg-muted rounded">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-sm font-medium">Nome *</label>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Nome do contato"
            />
          </div>

          <div>
            <label className="text-sm font-medium">Telefone *</label>
            <Input
              value={form.phone_number}
              onChange={(e) => setForm({ ...form, phone_number: e.target.value })}
              placeholder="+55 11 99999-9999"
            />
          </div>

          <div>
            <label className="text-sm font-medium">Grupo</label>
            <Input
              value={form.group_name ?? "outros"}
              onChange={(e) => setForm({ ...form, group_name: e.target.value.toLowerCase().replace(/\s+/g, "_") })}
              placeholder="Ex: familia, amigos, funcionarios"
            />
            <p className="text-xs text-muted-foreground mt-1">Digite o nome do grupo (ex: familia, amigos, clientes)</p>
          </div>

          <div>
            <label className="text-sm font-medium">Observações</label>
            <Input
              value={form.notes ?? ""}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              placeholder="Notas opcionais"
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose} className="flex-1">
              Cancelar
            </Button>
            <Button type="submit" className="flex-1" disabled={createMutation.isPending || updateMutation.isPending}>
              {contact ? "Salvar" : "Criar"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
