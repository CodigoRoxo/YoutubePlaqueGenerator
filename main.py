import re
import requests
from PIL import Image, ImageDraw, ImageFont
import os
from urllib.parse import unquote

def get_channel_info(channel_input):
    """
    Obtém o nome do canal e número de inscritos de um canal do YouTube.
    Retorna (subscriber_count, channel_name, url).
    """
    try:
        # Extrai o identificador do canal da URL ou usa o input diretamente
        if 'youtube.com' in channel_input or 'youtu.be' in channel_input:
            # Tenta extrair o handle ou nome do canal
            if '/@' in channel_input:
                channel_name = channel_input.split('/@')[1].split('/')[0].split('?')[0]
                url = f'https://www.youtube.com/@{channel_name}'
            elif '/channel/' in channel_input:
                channel_id = channel_input.split('/channel/')[1].split('/')[0].split('?')[0]
                url = f'https://www.youtube.com/channel/{channel_id}'
            elif '/c/' in channel_input:
                channel_name = channel_input.split('/c/')[1].split('/')[0].split('?')[0]
                url = f'https://www.youtube.com/c/{channel_name}'
            else:
                url = channel_input
        else:
            # Assume que é um handle ou nome
            channel_name = channel_input.replace('@', '')
            url = f'https://www.youtube.com/@{channel_name}'
        
        # Faz requisição ao canal
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Debug: salva o HTML para análise
        print(f"   Status da requisição: {response.status_code}")
        
        # PRIMEIRO: Extrai o nome do canal (sem @)
        channel_name = None
        name_patterns = [
            # Meta tag - mais confiável
            r'<meta\s+property="og:title"\s+content="([^"]+)"',
            r'<meta\s+name="title"\s+content="([^"]+)"',
            # JSON do YouTube
            r'"channelMetadataRenderer"[^}]*"title"\s*:\s*"([^"]+)"',
            r'"header"[^}]*"channelName"[^}]*"simpleText"\s*:\s*"([^"]+)"',
            r'"author"\s*:\s*"([^"]+)"',
        ]
        
        for i, pattern in enumerate(name_patterns):
            match = re.search(pattern, response.text, re.IGNORECASE | re.DOTALL)
            if match:
                potential_name = match.group(1).strip()
                # Ignora se for lixo comum
                if potential_name and potential_name not in ['Início', 'Home', 'YouTube'] and not re.search(r'\d+.*(?:subscriber|inscrito)', potential_name, re.IGNORECASE):
                    channel_name = potential_name
                    print(f"   ✓ Nome do canal encontrado (padrão {i+1}): '{channel_name}'")
                    break
        
        # SEGUNDO: Procura o número de inscritos na página
        patterns = [
            # Padrões JSON do YouTube
            r'"subscriberCountText".*?"simpleText"\s*:\s*"([^"]+)"',
            r'"subscriberCountText".*?"accessibility".*?"label"\s*:\s*"([^"]+)"',
            r'"label"\s*:\s*"([\d,\.]+\s*(?:mil|mi|[KMB])\s+(?:de\s+)?(?:subscriber|inscrito)[^"]*)"',
            # Padrões HTML
            r'yt-core-attributed-string[^>]*>([^<]*(?:subscriber|inscrito)[^<]*)<',
            r'subscriber-count[^>]*>([^<]+)<',
            # Padrões mais genéricos
            r'([\d,\.]+\s*(?:mil|mi|[KMB])?)\s+(?:de\s+)?(?:subscribers?|inscritos?)',
            r'"text"\s*:\s*"([\d,\.]+\s*(?:mil|mi|[KMB]))[^"]*(?:subscriber|inscrito)',
        ]
        
        for i, pattern in enumerate(patterns):
            matches = re.finditer(pattern, response.text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                sub_text = match.group(1).strip()
                print(f"   ✓ Padrão {i+1} encontrou: '{sub_text[:100]}'")
                
                # Extrai o número COM o sufixo (K, M, mi, mil, etc)
                number_match = re.search(r'([\d,\.]+\s*(?:mil|mi|[KMB])?)', sub_text, re.IGNORECASE)
                if number_match:
                    sub_number = number_match.group(1).strip()
                    print(f"   → Número extraído: '{sub_number}'")
                    count = parse_subscriber_count(sub_number)
                    if count > 0:
                        # Se não encontrou o nome do canal, usa fallback
                        if not channel_name:
                            channel_name = unquote(url.split('/@')[1]) if '/@' in url else 'Canal'
                        return count, channel_name, url
            
        # Se não encontrou, faz debug mais detalhado
        print("\n   [DEBUG] Buscando 'inscrito' e 'subscriber' no HTML...")
        
        # Busca em português
        inscrito_matches = re.findall(r'.{0,150}(?:inscrito|inscritos).{0,150}', response.text, re.IGNORECASE)[:5]
        if inscrito_matches:
            print("   Resultados com 'inscrito':")
            for match in inscrito_matches:
                # Procura números próximos
                if re.search(r'\d', match):
                    print(f"   • {match[:200]}")
        
        # Busca em inglês
        subscriber_matches = re.findall(r'.{0,150}subscriber.{0,150}', response.text, re.IGNORECASE)[:5]
        if subscriber_matches:
            print("   Resultados com 'subscriber':")
            for match in subscriber_matches:
                if re.search(r'\d', match):
                    print(f"   • {match[:200]}")
        
        return None, None, url
    
    except Exception as e:
        print(f"Erro ao obter informações do canal: {e}")
        return None, None, None

def parse_subscriber_count(sub_text):
    """
    Converte texto de inscritos para número.
    Exemplos:
    - "10.1K" -> 10100
    - "1.5M" -> 1500000
    - "1,23 mi" -> 1230000
    - "100K" -> 100000
    - "5.2K" -> 5200
    """
    # Substitui vírgula por ponto para padronizar decimais
    sub_text = sub_text.replace(',', '.')
    
    # Converte para maiúscula
    sub_text_upper = sub_text.upper()
    
    # Dicionário de multiplicadores (ordem importante - mais específicos primeiro!)
    # Usa regex para garantir match exato do sufixo
    multipliers = [
        (r'MILH[ÕOÃ]ES', 1_000_000),      # Milhões por extenso
        (r'BILH[ÕOÃ]ES', 1_000_000_000),  # Bilhões por extenso
        (r'MIL\b', 1_000),                 # Mil (com word boundary para não pegar "milhões")
        (r'BI\b', 1_000_000_000),          # Bi (bilhões abreviado)
        (r'MI\b', 1_000_000),              # Mi (milhões abreviado) 
        (r'M\b', 1_000_000),               # M = Millions
        (r'B\b', 1_000_000_000),           # B = Billions
        (r'K\b', 1_000),                   # K = Thousands
    ]
    
    # Verifica cada multiplicador usando regex
    for suffix_pattern, multiplier in multipliers:
        # Procura o número seguido do sufixo
        match = re.search(r'([\d.]+)\s*' + suffix_pattern + r'\b', sub_text_upper, re.IGNORECASE)
        if match:
            number_str = match.group(1)
            try:
                number = float(number_str)
                result = int(number * multiplier)
                return result
            except ValueError:
                continue
    
    # Se não tiver sufixo, converte diretamente
    try:
        clean_number = re.sub(r'[^\d.]', '', sub_text)
        return int(float(clean_number))
    except ValueError:
        return 0

def select_template(subscriber_count):
    """
    Seleciona o template apropriado baseado no número de inscritos.
    """
    if subscriber_count >= 50_000:
        return '50k.png'
    elif subscriber_count >= 10_000:
        return '10k.png'
    elif subscriber_count >= 1_000:
        return '1k.png'
    elif subscriber_count >= 500:
        return '500.png'
    else:
        return '100.png'

def create_youtube_plaque(channel_name, template_path, output_path='placa_gerada.png'):
    """
    Cria uma placa do YouTube personalizada com o nome do canal.
    """
    try:
        # Abre a imagem template
        img = Image.open(template_path)
        draw = ImageDraw.Draw(img)
        
        # Configurações de texto
        img_width, img_height = img.size
        print(f"   Dimensões da imagem: {img_width}x{img_height}")
        
        # Tenta usar uma fonte melhor, senão usa a padrão
        try:
            # Tenta fontes do sistema Windows (Poppins e outras modernas)
            font_paths = [
                'C:/Windows/Fonts/Poppins-Regular.ttf',
                'C:/Windows/Fonts/Poppins-Medium.ttf',
                'C:/Windows/Fonts/calibri.ttf',
                'C:/Windows/Fonts/arial.ttf',
                'C:/Windows/Fonts/seguisb.ttf',  # Segoe UI Semibold
                'C:/Windows/Fonts/segoeui.ttf',
            ]
            font = None
            font_size = 50  # Reduzido de 60 para 48
            for font_path in font_paths:
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, font_size)
                    print(f"   Fonte carregada: {font_path}")
                    break
            
            if font is None:
                font = ImageFont.load_default()
                print(f"   Usando fonte padrão")
        except Exception as e:
            font = ImageFont.load_default()
            print(f"   Erro ao carregar fonte, usando padrão: {e}")
        
        # Calcula posição do texto (centralizado horizontalmente, mais abaixo verticalmente)
        # Usa textbbox para PIL mais recente
        try:
            bbox = draw.textbbox((0, 0), channel_name, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except:
            # Fallback para versões antigas
            text_width, text_height = draw.textsize(channel_name, font=font)
        
        x = (img_width - text_width) // 2
        # Posiciona o texto mais abaixo (65% da altura)
        y = int((img_height * 0.734) - (text_height // 2))
        
        print(f"   Texto: '{channel_name}'")
        print(f"   Posição: x={x}, y={y}")
        print(f"   Tamanho do texto: {text_width}x{text_height}")
        
        # Desenha o texto (somente branco, sem sombra)
        draw.text((x, y), channel_name, font=font, fill='white')
        print(f"   ✓ Texto desenhado")
        
        # Salva a imagem
        img.save(output_path)
        print(f"\n✓ Placa criada com sucesso: {output_path}")
        
        # Abre a imagem gerada
        img.show()
        
    except Exception as e:
        print(f"Erro ao criar placa: {e}")

def main():
    print("=" * 60)
    print(" GERADOR DE PLACAS DO YOUTUBE ".center(60))
    print("=" * 60)
    print()
    
    # Solicita o canal
    channel_input = input("Digite a URL ou nome do canal do YouTube (@canal): ").strip()
    
    if not channel_input:
        print("❌ Canal não informado!")
        return
    
    print(f"\n🔍 Buscando informações do canal...")
    
    # Obtém número de inscritos e nome do canal
    subscriber_count, channel_name, channel_url = get_channel_info(channel_input)
    
    if subscriber_count is None or channel_name is None:
        print("❌ Não foi possível obter o número de inscritos do canal.")
        print("   Verifique se a URL/nome está correto e tente novamente.")
        return
    
    print(f"\n📊 Canal: {channel_name}")
    print(f"👥 Inscritos: {subscriber_count:,}".replace(',', '.'))
    
    # Seleciona template
    template_name = select_template(subscriber_count)
    template_path = os.path.join('TemplatePlacas', template_name)
    
    print(f"🏆 Template selecionado: {template_name}")
    
    if not os.path.exists(template_path):
        print(f"❌ Template não encontrado: {template_path}")
        return
    
    # Cria a placa
    print(f"\n🎨 Criando placa personalizada...")
    # Remove caracteres problemáticos do nome do arquivo
    safe_filename = re.sub(r'[<>:"/\\|?*@]', '', channel_name).replace(' ', '_')
    output_filename = f"placa_{safe_filename}.png"
    create_youtube_plaque(channel_name, template_path, output_filename)
    
    print("\n" + "=" * 60)
    print(" Processo concluído! ".center(60))
    print("=" * 60)

if __name__ == "__main__":
    main()
