import uuid
from datetime import datetime, timezone, date
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import Column, String, DateTime, Date, ForeignKey, Text, JSON, Float, Integer
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector



class Base(DeclarativeBase):
    pass



# --- ENUMS ---
class ProcessingStatus(PyEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"



class MediaType(PyEnum):
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"



# --- TABLES ---

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True) # Project names must be unique
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Link to files
    files: Mapped[List["MediaFile"]] = relationship("MediaFile", back_populates="project", cascade="all, delete-orphan")



class MediaFile(Base):
    __tablename__ = "media_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(1024), nullable=True) 
    media_type: Mapped[MediaType] = mapped_column(ENUM(MediaType, name="media_type_enum"))
    status: Mapped[ProcessingStatus] = mapped_column(ENUM(ProcessingStatus, name="status_enum"), default=ProcessingStatus.PENDING)
    description: Mapped[str] = mapped_column(String(1000))

    event: Mapped[str] = mapped_column(String(1000), nullable=True)
    event_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    # Metadata
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc) 
    )

    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("projects.id"), nullable=True)
    
    # Relationships
    transcription: Mapped["Transcription"] = relationship(
                                                            "Transcription", 
                                                            back_populates="media_file", 
                                                            uselist=False,
                                                            cascade="all, delete-orphan" 
                                                        )
    project: Mapped["Project"] = relationship("Project", back_populates="files")



class Transcription(Base):
    __tablename__ = "transcriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    media_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("media_files.id"))
    
    # Content
    full_text: Mapped[str] = mapped_column(Text) # The merged, clean text
    language: Mapped[str] = mapped_column(String(100), default="fr")
    
    # Metadata
    model_used: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc) 
    )

    # Relationships
    media_file: Mapped["MediaFile"] = relationship("MediaFile", back_populates="transcription")
    chunks: Mapped[List["TranscriptionChunk"]] = relationship("TranscriptionChunk", back_populates="transcription", cascade="all, delete-orphan")



class TranscriptionChunk(Base):
    """
    Stores individual chunks for RAG (Vector Search).
    """
    __tablename__ = "transcription_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transcription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transcriptions.id"))
    
    chunk_index: Mapped[int] = mapped_column(Integer) # To keep order (0, 1, 2...)
    text_content: Mapped[str] = mapped_column(Text)
    
    # The Vector for RAG (1536 dims for OpenAI, 768 for Gemini usually)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(1536), nullable=True)
    
    # Relationships
    transcription: Mapped["Transcription"] = relationship("Transcription", 
                                                          back_populates="chunks")