# Backend 

This is the backend of the *image finder*. It is written in *python* and *FastAPI*. 

## Structure

This is the structure of the backend: blablabla

## Installment

For local employment:

```bash
cd backend # Make sure you are in the correct dir

python -m venv venv

source venv/bin/activate

pip install -r requirements.txt
```

Add .env file with [Mapilliary API](https://www.mapillary.com/developer/api-documentation):

```
touch .env # create .env file in backend dir

MAPILLARY_TOKEN=<YOUR_API_KEY>
```

To run the backend server:

```bash
uvicorn main:app --host 0.0.0.0 --reload
```

## Data

blablabla