from pydantic import Field, AliasChoices, BaseModel as BaseSettings


class Settings(BaseSettings):
    request_service_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("REQUEST_SERVICE_URL"),
    )
    access_service_url: str = Field(
        default="http://localhost:8001",
        validation_alias=AliasChoices("ACCESS_SERVICE_URL"),
    )
    rabbitmq_url: str = Field(
        default="amqp://guest:guest@localhost/",
        validation_alias=AliasChoices("RABBITMQ_URL"),
    )

    requests_queue: str = Field(
        default="access_requests",
        validation_alias=AliasChoices("REQUESTS_QUEUE"),
    )


settings = Settings()
