from pydantic import BaseModel, Field


class WriteBody(BaseModel):
    path: str = Field(..., description="Absolute or relative file path inside MCP_ALLOWED_ROOTS.")
    content: str = Field(default="", description="Text file content (UTF-8 or provided encoding).")
    encoding: str = Field(default="utf-8", description="Write encoding, e.g. utf-8.")
    create_parents: bool = Field(
        default=False,
        description="If true, create missing parent directories before writing.",
    )


class MkdirBody(BaseModel):
    path: str
    parents: bool = Field(default=False, description="If true, behaves like mkdir -p.")


class DeleteBody(BaseModel):
    path: str = Field(..., description="File or empty directory to delete.")


class RenameBody(BaseModel):
    from_path: str = Field(..., description="Existing source path.")
    to_path: str = Field(..., description="Target path (must not exist; parent directory must exist).")
