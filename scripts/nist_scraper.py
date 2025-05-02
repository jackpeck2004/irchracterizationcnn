import requests

with open('../nist_dataset/ids.txt', 'r') as file:
    nist_ids = file.readlines()
    nist_ids = [line.strip() for line in nist_ids]

    for nist_id in nist_ids:
        url = f'https://webbook.nist.gov/cgi/inchi?JCAMP={nist_id}&Index=0&Type=IR'
        response = requests.get(url)
        if response.status_code == 200:
            with open(f'../nist_dataset/jcamp/{nist_id}.jdx', 'w') as output_file:
                output_file.write(response.text)
                print(f'Successfully downloaded {nist_id}')
        else:
            print(f'Failed to download {nist_id}')


