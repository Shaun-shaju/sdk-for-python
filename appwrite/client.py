import io
import requests
import os
from .input_file import InputFile
from .exception import AppwriteException

class Client:
    def __init__(self):
        self._chunk_size = 5*1024*1024
        self._self_signed = False
        self._endpoint = 'https://HOSTNAME/v1'
        self._global_headers = {
            'content-type': '',
            'x-sdk-name': 'Python',
            'x-sdk-platform': 'server',
            'x-sdk-language': 'python',
            'x-sdk-version': '1.0.0',
            'X-Appwrite-Response-Format' : '1.0.0',
        }

    def set_self_signed(self, status=True):
        self._self_signed = status
        return self

    def set_endpoint(self, endpoint):
        self._endpoint = endpoint
        return self

    def add_header(self, key, value):
        self._global_headers[key.lower()] = value
        return self

    def set_project(self, value):
        """Your project ID"""

        self._global_headers['x-appwrite-project'] = value
        return self

    def set_key(self, value):
        """Your secret API key"""

        self._global_headers['x-appwrite-key'] = value
        return self

    def set_jwt(self, value):
        """Your secret JSON Web Token"""

        self._global_headers['x-appwrite-jwt'] = value
        return self

    def set_locale(self, value):
        self._global_headers['x-appwrite-locale'] = value
        return self

    def call(self, method, path='', headers=None, params=None):
        if headers is None:
            headers = {}

        if params is None:
            params = {}

        data = {}
        json = {}
        files = {}
        stringify = False
        
        headers = {**self._global_headers, **headers}

        if method != 'get':
            data = params
            params = {}

        if headers['content-type'].startswith('application/json'):
            json = data
            data = {}

        if headers['content-type'].startswith('multipart/form-data'):
            del headers['content-type']
            stringify = True
            for key in data.copy():
                if isinstance(data[key], InputFile):
                    files[key] = (data[key].filename, data[key].data)
                    del data[key]
        response = None
        try:
            response = requests.request(  # call method dynamically https://stackoverflow.com/a/4246075/2299554
                method=method,
                url=self._endpoint + path,
                params=self.flatten(params, stringify=stringify),
                data=self.flatten(data),
                json=json,
                files=files,
                headers=headers,
                verify=(not self._self_signed),
            )

            response.raise_for_status()

            content_type = response.headers['Content-Type']

            if content_type.startswith('application/json'):
                return response.json()

            return response._content
        except Exception as e:
            if response != None:
                content_type = response.headers['Content-Type']
                if content_type.startswith('application/json'):
                    raise AppwriteException(response.json()['message'], response.status_code, response.json().get('type'), response.json())
                else:
                    raise AppwriteException(response.text, response.status_code)
            else:
                raise AppwriteException(e)

    def chunked_upload(
        self,
        path,
        headers = None,
        params = None,
        param_name = '',
        on_progress = None,
        upload_id = ''
    ):
        input_file = params[param_name]

        if input_file.source_type == 'path':
            size = os.stat(input_file.path).st_size
            input = open(input_file.path, 'rb')
        elif input_file.source_type == 'bytes':
            size = len(input_file.data)
            input = input_file.data

        if size < self._chunk_size:
            if input_file.source_type == 'path':
                input_file.data = input.read()

            params[param_name] = input_file
            return self.call(
                'post',
                path,
                headers,
                params
            )

        offset = 0
        counter = 0

        if upload_id != 'unique()':
            try:
                result = self.call('get', path + '/' + upload_id, headers)
                counter = result['chunksUploaded']
            except:
                pass

        if counter > 0:
            offset = counter * self._chunk_size
            input.seek(offset)

        while offset < size:
            if input_file.source_type == 'path':
                input_file.data = input.read(self._chunk_size) or input.read(size - offset)
            elif input_file.source_type == 'bytes':
                if offset + self._chunk_size < size:
                    end = offset + self._chunk_size
                else:
                    end = size - offset
                input_file.data = input[offset:end]

            params[param_name] = input_file
            headers["content-range"] = f'bytes {offset}-{min((offset + self._chunk_size) - 1, size)}/{size}'

            result = self.call(
                'post',
                path,
                headers,
                params,
            )
            
            offset = offset + self._chunk_size
            
            if "$id" in result: 
                headers["x-appwrite-id"] = result["$id"]

            if on_progress is not None:
                end = min((((counter * self._chunk_size) + self._chunk_size) - 1), size)
                on_progress({
                    "$id": result["$id"],
                    "progress": min(offset, size)/size * 100,
                    "sizeUploaded": end+1,
                    "chunksTotal": result["chunksTotal"],
                    "chunksUploaded": result["chunksUploaded"],
                })

            counter = counter + 1

        return result

    def flatten(self, data, prefix='', stringify=False):
        output = {}
        i = 0

        for key in data:
            value = data[key] if isinstance(data, dict) else key
            finalKey = prefix + '[' + key +']' if prefix else key
            finalKey = prefix + '[' + str(i) +']' if isinstance(data, list) else finalKey
            i += 1
            
            if isinstance(value, list) or isinstance(value, dict):
                output = {**output, **self.flatten(value, finalKey, stringify)}
            else:
                if stringify:
                    output[finalKey] = str(value)
                else:
                    output[finalKey] = value

        return output

