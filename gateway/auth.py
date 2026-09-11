import os
import requests
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidSignatureError, InvalidTokenError
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Load Entra ID credentials from environment
TENANT_ID = os.getenv("AZURE_TENANT_ID")
print(f"[Auth] Using Azure Tenant ID: {TENANT_ID}")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
print(f"[Auth] Using Azure Client ID: {CLIENT_ID}")

# Cache for Microsoft JWKS keys to prevent calling API on every request
_jwks_cache = None
_jwks_last_fetch = 0

def get_ms_public_keys():
    global _jwks_cache, _jwks_last_fetch
    import time
    now = time.time()
    
    # Cache keys for 1 hour to avoid excessive remote calls
    if _jwks_cache is None or now - _jwks_last_fetch > 3600:
        tenant = TENANT_ID or "common"
        url = f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"
        try:
            res = requests.get(url, timeout=5)
            res.raise_for_status()
            _jwks_cache = res.json()
            _jwks_last_fetch = now
        except Exception as e:
            print(f"[Auth Error] Failed to fetch JWKS keys from Microsoft: {e}")
            if _jwks_cache is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication server public keys unavailable."
                )
    return _jwks_cache

def verify_m365_token(token: str) -> dict:
    """
    Verifies M365 (Microsoft Entra ID) JWT token and returns user details.
    """
    try:
        # Get token header to extract kid (key id)
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            raise InvalidTokenError("Missing key ID (kid) in token header.")
            
        # Get public keys
        jwks = get_ms_public_keys()
        
        # Find matching key
        matching_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                matching_key = key
                break
                
        if not matching_key:
            raise InvalidSignatureError("Public key not found for token kid.")
            
        # Construct PyJWT RSA Public Key
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(matching_key)
        
        # Determine expected issuer
        tenant = TENANT_ID or "common"
        issuer = f"https://login.microsoftonline.com/{tenant}/v2.0"
        
        # If tenant is common, we bypass strict issuer match (as issuer is tenant-specific)
        verify_opts = {"verify_iss": False if tenant == "common" else True}
        
        # Decode and verify
        audience = CLIENT_ID if CLIENT_ID else None
        
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer if verify_opts["verify_iss"] else None,
            options=verify_opts
        )
        
        # Extract user details
        email = claims.get("preferred_username") or claims.get("email") or claims.get("upn")
        name = claims.get("name")
        
        # Look for employee ID in common Entra ID claim paths
        employee_id = (
            claims.get("employeeid") or 
            claims.get("employee_id") or 
            claims.get("extension_employeeid")
        )
        
        if not email:
            raise InvalidTokenError("Missing user identifier (email/upn) in token claims.")
            
        return {
            "email": email,
            "name": name or email.split("@")[0],
            "employee_id": employee_id or "N/A",
            "claims": claims
        }
        
    except ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail=f"Token expired: {str(e)}")
    except InvalidSignatureError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token signature: {str(e)}")
    except InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

# FastAPI Dependency
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    # If a master API key is configured and matches, we can allow CLI bypass (e.g. system deployments)
    # but for M365 authentication OIDC we decode the token.
    token = credentials.credentials
    master_key = os.getenv("CREWAI_AMP_KEY", "super-secret-company-key")
    
    if token == master_key:
        # System/Master key fallback
        return {
            "email": "system@company.com",
            "name": "System Deployer",
            "employee_id": "SYSTEM",
            "claims": {}
        }
        
    # Verify M365 OIDC token
    return verify_m365_token(token)
