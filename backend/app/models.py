from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Table, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def agora() -> datetime:
    """Horário atual em UTC, sem tzinfo (padrão de armazenamento do sistema)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Escola(Base):
    __tablename__ = "escolas"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    # professor que cadastrou (área particular dele); vazio = cadastrada pelo administrador
    criado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL", use_alter=True),
                                                   nullable=True, index=True)
    turmas: Mapped[list["Turma"]] = relationship(back_populates="escola", cascade="all, delete-orphan")


class Turma(Base):
    __tablename__ = "turmas"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100))
    ano_letivo: Mapped[str | None] = mapped_column(String(10), nullable=True)
    escola_id: Mapped[int] = mapped_column(ForeignKey("escolas.id", ondelete="CASCADE"))
    professor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
                                                     index=True)  # dono da turma
    escola: Mapped[Escola] = relationship(back_populates="turmas")
    professor: Mapped["Usuario | None"] = relationship(foreign_keys=[professor_id])
    matriculas: Mapped[list["Matricula"]] = relationship(back_populates="turma", cascade="all, delete-orphan")


class Disciplina(Base):
    __tablename__ = "disciplinas"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100))
    escola_id: Mapped[int | None] = mapped_column(ForeignKey("escolas.id", ondelete="CASCADE"), nullable=True)
    criado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL", use_alter=True),
                                                   nullable=True, index=True)
    escola: Mapped[Escola | None] = relationship()


class Vinculo(Base):
    """Professor x escola x disciplina: define o que cada professor pode ver e usar."""
    __tablename__ = "vinculos"
    __table_args__ = (UniqueConstraint("professor_id", "escola_id", "disciplina_id", name="uq_vinculo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    professor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    escola_id: Mapped[int] = mapped_column(ForeignKey("escolas.id", ondelete="CASCADE"))
    disciplina_id: Mapped[int] = mapped_column(ForeignKey("disciplinas.id", ondelete="CASCADE"))
    escola: Mapped[Escola] = relationship()
    disciplina: Mapped[Disciplina] = relationship()


class Matricula(Base):
    """Aluno x turma. Um mesmo aluno (RM) pode estar em turmas de professores diferentes."""
    __tablename__ = "matriculas"
    __table_args__ = (UniqueConstraint("turma_id", "aluno_id", name="uq_matricula"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    turma_id: Mapped[int] = mapped_column(ForeignKey("turmas.id", ondelete="CASCADE"), index=True)
    aluno_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    lote_importacao: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    turma: Mapped[Turma] = relationship(back_populates="matriculas")
    aluno: Mapped["Usuario"] = relationship(back_populates="matriculas")


class Meta(Base):
    __tablename__ = "meta"
    chave: Mapped[str] = mapped_column(String(50), primary_key=True)
    valor: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    login: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(200))
    papel: Mapped[str] = mapped_column(String(20))  # admin | professor | aluno
    turma_id: Mapped[int | None] = mapped_column(ForeignKey("turmas.id", ondelete="SET NULL", use_alter=True), nullable=True)  # legado
    matriculas: Mapped[list[Matricula]] = relationship(back_populates="aluno", cascade="all, delete-orphan")
    vinculos: Mapped[list[Vinculo]] = relationship(cascade="all, delete-orphan", foreign_keys="Vinculo.professor_id")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    lote_importacao: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)


class Avaliacao(Base):
    __tablename__ = "avaliacoes"
    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    tipo: Mapped[str] = mapped_column(String(20), default="prova")  # prova | simulado | teste
    escola_id: Mapped[int] = mapped_column(ForeignKey("escolas.id"))
    turma_id: Mapped[int] = mapped_column(ForeignKey("turmas.id"))
    disciplina_id: Mapped[int] = mapped_column(ForeignKey("disciplinas.id"))
    professor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    inicio: Mapped[datetime] = mapped_column(DateTime)
    fim: Mapped[datetime] = mapped_column(DateTime)
    duracao_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embaralhar_questoes: Mapped[bool] = mapped_column(Boolean, default=True)
    embaralhar_alternativas: Mapped[bool] = mapped_column(Boolean, default=True)
    # apos_fim: feedback liberado quando a avaliação encerra | apos_envio: logo após enviar | manual
    liberar_resultado: Mapped[str] = mapped_column(String(20), default="apos_fim")
    resultado_liberado: Mapped[bool] = mapped_column(Boolean, default=False)
    publicada: Mapped[bool] = mapped_column(Boolean, default=False)
    # nota total da avaliação, distribuída entre as questões conforme o peso de cada uma
    nota_total: Mapped[float] = mapped_column(Float, default=10.0)
    peso_objetiva: Mapped[float] = mapped_column(Float, default=1.0)       # peso sugerido para novas objetivas
    peso_dissertativa: Mapped[float] = mapped_column(Float, default=2.0)   # peso sugerido para novas dissertativas
    monitorar: Mapped[bool] = mapped_column(Boolean, default=True)         # registrar saídas de aba/janela
    # dissertativas: desligada (só palavras-chave) | sugestao (IA sugere, professor confirma)
    # | automatica (vale a nota da IA; palavras-chave ficam como reserva se a IA falhar)
    correcao_ia: Mapped[str] = mapped_column(String(20), default="desligada")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)

    escola: Mapped[Escola] = relationship()
    turma: Mapped[Turma] = relationship()
    disciplina: Mapped[Disciplina] = relationship()
    questoes: Mapped[list["Questao"]] = relationship(
        back_populates="avaliacao", cascade="all, delete-orphan", order_by="Questao.ordem")
    tentativas: Mapped[list["Tentativa"]] = relationship(back_populates="avaliacao", cascade="all, delete-orphan")


class Questao(Base):
    __tablename__ = "questoes"
    id: Mapped[int] = mapped_column(primary_key=True)
    avaliacao_id: Mapped[int] = mapped_column(ForeignKey("avaliacoes.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))  # objetiva | dissertativa
    enunciado: Mapped[str] = mapped_column(Text)
    peso: Mapped[float] = mapped_column(Float, default=1.0)     # definido pelo professor
    pontos: Mapped[float] = mapped_column(Float, default=1.0)   # calculado: nota_total * peso / soma dos pesos
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    explicacao: Mapped[str | None] = mapped_column(Text, nullable=True)  # mostrada no feedback
    gabarito_texto: Mapped[str | None] = mapped_column(Text, nullable=True)  # resposta esperada (dissertativa)
    palavras_chave: Mapped[list | None] = mapped_column(JSON, nullable=True)  # ["fotossíntese", "luz|luminosa"]

    avaliacao: Mapped[Avaliacao] = relationship(back_populates="questoes")
    alternativas: Mapped[list["Alternativa"]] = relationship(
        back_populates="questao", cascade="all, delete-orphan", order_by="Alternativa.ordem")


class Alternativa(Base):
    __tablename__ = "alternativas"
    id: Mapped[int] = mapped_column(primary_key=True)
    questao_id: Mapped[int] = mapped_column(ForeignKey("questoes.id", ondelete="CASCADE"), index=True)
    texto: Mapped[str] = mapped_column(Text)
    correta: Mapped[bool] = mapped_column(Boolean, default=False)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    questao: Mapped[Questao] = relationship(back_populates="alternativas")


class Tentativa(Base):
    __tablename__ = "tentativas"
    __table_args__ = (UniqueConstraint("avaliacao_id", "aluno_id", name="uq_tentativa_aluno"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    avaliacao_id: Mapped[int] = mapped_column(ForeignKey("avaliacoes.id", ondelete="CASCADE"), index=True)
    aluno_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    iniciado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    prazo: Mapped[datetime] = mapped_column(DateTime)
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    envio_automatico: Mapped[bool] = mapped_column(Boolean, default=False)
    ordem_questoes: Mapped[list] = mapped_column(JSON)          # [questao_id, ...] embaralhado
    ordem_alternativas: Mapped[dict] = mapped_column(JSON)      # {"questao_id": [alt_id, ...]}
    nota: Mapped[float | None] = mapped_column(Float, nullable=True)
    nota_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    # ---- metadados de acesso e monitoramento ----
    ip_inicio: Mapped[str | None] = mapped_column(String(64), nullable=True)
    navegador_inicio: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_envio: Mapped[str | None] = mapped_column(String(64), nullable=True)
    navegador_envio: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tela: Mapped[str | None] = mapped_column(String(40), nullable=True)
    qtd_acessos: Mapped[int] = mapped_column(Integer, default=1)          # vezes que abriu/reabriu a prova
    qtd_saidas: Mapped[int] = mapped_column(Integer, default=0)           # trocas de aba / janela
    tempo_fora_seg: Mapped[int] = mapped_column(Integer, default=0)
    qtd_fechamentos: Mapped[int] = mapped_column(Integer, default=0)      # fechou/recarregou a página
    outro_dispositivo: Mapped[bool] = mapped_column(Boolean, default=False)

    avaliacao: Mapped[Avaliacao] = relationship(back_populates="tentativas")
    aluno: Mapped[Usuario] = relationship()
    respostas: Mapped[list["Resposta"]] = relationship(back_populates="tentativa", cascade="all, delete-orphan")
    eventos: Mapped[list["Evento"]] = relationship(back_populates="tentativa", cascade="all, delete-orphan",
                                                   order_by="Evento.em")


class Evento(Base):
    """Linha do tempo da tentativa: início, saídas de aba, retornos, fechamentos, envio."""
    __tablename__ = "eventos"
    id: Mapped[int] = mapped_column(primary_key=True)
    tentativa_id: Mapped[int] = mapped_column(ForeignKey("tentativas.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(30))
    em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    duracao_seg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    navegador: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detalhe: Mapped[str | None] = mapped_column(String(300), nullable=True)
    tentativa: Mapped[Tentativa] = relationship(back_populates="eventos")


class Resposta(Base):
    __tablename__ = "respostas"
    __table_args__ = (UniqueConstraint("tentativa_id", "questao_id", name="uq_resposta_questao"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tentativa_id: Mapped[int] = mapped_column(ForeignKey("tentativas.id", ondelete="CASCADE"), index=True)
    questao_id: Mapped[int] = mapped_column(ForeignKey("questoes.id", ondelete="CASCADE"))
    alternativa_id: Mapped[int | None] = mapped_column(ForeignKey("alternativas.id", ondelete="SET NULL"), nullable=True)
    texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    pontos_auto: Mapped[float | None] = mapped_column(Float, nullable=True)
    situacao: Mapped[str | None] = mapped_column(String(20), nullable=True)  # certa | errada | parcial | em_branco
    feedback_auto: Mapped[str | None] = mapped_column(Text, nullable=True)
    pontos_revisados: Mapped[float | None] = mapped_column(Float, nullable=True)
    comentario_professor: Mapped[str | None] = mapped_column(Text, nullable=True)
    # correção por palavras-chave guardada à parte (é a reserva quando a IA falha)
    pontos_chaves: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback_chaves: Mapped[str | None] = mapped_column(Text, nullable=True)
    # correção por IA: pendente | processando | ok | falhou
    ia_status: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    ia_pontos: Mapped[float | None] = mapped_column(Float, nullable=True)
    ia_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    ia_provedor: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ia_erro: Mapped[str | None] = mapped_column(String(300), nullable=True)
    ia_tentativas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ia_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    tentativa: Mapped[Tentativa] = relationship(back_populates="respostas")
    questao: Mapped[Questao] = relationship()

    @property
    def pontos_finais(self) -> float:
        if self.pontos_revisados is not None:
            return self.pontos_revisados
        return self.pontos_auto or 0.0


class Imagem(Base):
    """Imagem usada no enunciado ou nas alternativas. O texto da questão guarda o marcador [imagem:CHAVE]."""
    __tablename__ = "imagens"
    id: Mapped[int] = mapped_column(primary_key=True)
    chave: Mapped[str] = mapped_column(String(40), unique=True, index=True)  # aleatória: não dá para adivinhar
    dono_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    mime: Mapped[str] = mapped_column(String(40))
    largura: Mapped[int | None] = mapped_column(Integer, nullable=True)
    altura: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dados: Mapped[bytes] = mapped_column(LargeBinary)
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
