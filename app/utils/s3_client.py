"""
AWS S3 client for chat history archival.

Provides methods to upload and retrieve chat history from S3.
Only used when AWS credentials are configured.
"""
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.exceptions import ClientError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("boto3 not installed. S3 functionality disabled.")


class S3Client:
    """AWS S3 client for chat history storage."""

    def __init__(
        self,
        region: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: Optional[str] = None,
        prefix: str = "chat-history",
    ):
        """
        Initialize S3 client.

        Args:
            region: AWS region
            access_key: AWS access key ID
            secret_key: AWS secret access key
            bucket: S3 bucket name
            prefix: S3 key prefix for chat history
        """
        self.region = region
        self.bucket = bucket
        self.prefix = prefix

        if not BOTO3_AVAILABLE or not all([region, access_key, secret_key, bucket]):
            logger.info("S3 client not configured. Chat history archival disabled.")
            self.client = None
            return

        try:
            self.client = boto3.client(
                "s3",
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
            logger.info("S3 client initialized for bucket: %s", bucket)
        except Exception as e:
            logger.error("Failed to initialize S3 client: %s", e)
            self.client = None

    def _get_key(self, user_id: str, session_id: str, timestamp: datetime) -> str:
        """
        Generate S3 object key.

        Args:
            user_id: User ID
            session_id: Session ID
            timestamp: Message timestamp

        Returns:
            S3 object key path
        """
        date_str = timestamp.strftime("%Y/%m/%d")
        return f"{self.prefix}/{user_id}/{session_id}/{date_str}/{timestamp.isoformat()}.json"

    async def save_message(
        self,
        user_id: str,
        session_id: str,
        message: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        Save a single chat message to S3.

        Args:
            user_id: User ID
            session_id: Session ID
            message: Message dict with role, content, etc.
            timestamp: Message timestamp (defaults to now)

        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            logger.debug("S3 client not configured, skipping message archival")
            return False

        try:
            if timestamp is None:
                timestamp = datetime.utcnow()

            key = self._get_key(user_id, session_id, timestamp)

            # Prepare message data
            message_data = {
                "user_id": user_id,
                "session_id": session_id,
                "timestamp": timestamp.isoformat(),
                "message": message,
            }

            # Upload to S3
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(message_data, indent=2),
                ContentType="application/json",
            )

            logger.debug("Message saved to S3: %s", key)
            return True

        except ClientError as e:
            logger.error("Failed to save message to S3: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error saving message to S3: %s", e)
            return False

    async def save_session_history(
        self,
        user_id: str,
        session_id: str,
        messages: list,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        Save entire session history to S3.

        Args:
            user_id: User ID
            session_id: Session ID
            messages: List of messages
            timestamp: Save timestamp (defaults to now)

        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            logger.debug("S3 client not configured, skipping session archival")
            return False

        try:
            if timestamp is None:
                timestamp = datetime.utcnow()

            date_str = timestamp.strftime("%Y/%m/%d")
            key = f"{self.prefix}/{user_id}/{session_id}/{date_str}/session.json"

            # Prepare session data
            session_data = {
                "user_id": user_id,
                "session_id": session_id,
                "saved_at": timestamp.isoformat(),
                "message_count": len(messages),
                "messages": messages,
            }

            # Upload to S3
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(session_data, indent=2),
                ContentType="application/json",
            )

            logger.info("Session history saved to S3: %s", key)
            return True

        except ClientError as e:
            logger.error("Failed to save session history to S3: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error saving session history to S3: %s", e)
            return False

    async def get_session_history(
        self, user_id: str, session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve session history from S3.

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            Session data dict or None if not found
        """
        if not self.client:
            return None

        try:
            # Try to get the latest session.json file
            # This is a simplified approach - in production, you'd list objects and get the latest
            prefix = f"{self.prefix}/{user_id}/{session_id}/"

            response = self.client.list_objects_v2(
                Bucket=self.bucket, Prefix=prefix, MaxKeys=100
            )

            if "Contents" not in response:
                return None

            # Get the most recent session.json
            session_keys = [
                obj["Key"]
                for obj in response["Contents"]
                if obj["Key"].endswith("session.json")
            ]

            if not session_keys:
                return None

            latest_key = sorted(session_keys)[-1]

            # Download the file
            obj = self.client.get_object(Bucket=self.bucket, Key=latest_key)
            data = json.loads(obj["Body"].read().decode("utf-8"))

            return data

        except ClientError as e:
            logger.error("Failed to get session history from S3: %s", e)
            return None
        except Exception as e:
            logger.error("Unexpected error getting session history from S3: %s", e)
            return None

    async def delete_session_history(self, user_id: str, session_id: str) -> bool:
        """
        Delete session history from S3.

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            return False

        try:
            prefix = f"{self.prefix}/{user_id}/{session_id}/"

            # List all objects with this prefix
            response = self.client.list_objects_v2(
                Bucket=self.bucket, Prefix=prefix
            )

            if "Contents" not in response:
                return True  # Nothing to delete

            # Delete all objects
            objects_to_delete = [{"Key": obj["Key"]} for obj in response["Contents"]]

            self.client.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": objects_to_delete},
            )

            logger.info("Session history deleted from S3: %s", session_id)
            return True

        except ClientError as e:
            logger.error("Failed to delete session history from S3: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error deleting session history from S3: %s", e)
            return False


# Create singleton instance (will be initialized with app settings)
_s3_client: Optional[S3Client] = None


def get_s3_client() -> Optional[S3Client]:
    """
    Get or create S3 client singleton.

    Returns:
        S3Client instance or None if not configured
    """
    global _s3_client
    if _s3_client is None:
        from app.config import get_settings

        settings = get_settings()

        if settings.is_aws_configured and settings.S3_BUCKET:
            _s3_client = S3Client(
                region=settings.AWS_REGION,
                access_key=settings.AWS_ACCESS_KEY_ID,
                secret_key=settings.AWS_SECRET_ACCESS_KEY,
                bucket=settings.S3_BUCKET,
                prefix=settings.S3_PREFIX,
            )
        else:
            _s3_client = S3Client()  # Disabled client

    return _s3_client
