"""
Creative Generation Agent (GPT-5.4-Nano)

This agent is responsible for:
1. Generating new ad creatives based on historical data
2. Creating compelling copy optimized for conversions
3. Finding similar successful ads for inspiration
4. Generating images using MCP vision tools
"""

import os
import json
import logging
from typing import Dict, List, Optional
from flask import Flask, request, jsonify
import openai
import redis
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
with open('/home/runner/work/20_03/20_03/config/config.json', 'r') as f:
    config = json.load(f)

# Initialize OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

# Initialize Redis
redis_client = redis.Redis(
    host=config['redis']['host'],
    port=config['redis']['port'],
    db=config['redis']['db'],
    decode_responses=True
)

class CreativeAgent:
    def __init__(self):
        self.model = config['subagents']['creative_agent']['model']
        self.temperature = config['subagents']['creative_agent']['temperature']
        self.max_tokens = config['subagents']['creative_agent']['max_tokens']

    def generate_creative(self, task_data: Dict) -> Dict:
        """Generate new creative based on task requirements"""
        try:
            # Get similar ads from RAG
            similar_ads = self._find_similar_ads(task_data.get('target_audience'))

            # Get historical performance data
            performance_data = self._get_performance_data(task_data.get('campaign_id'))

            # Generate copy
            copy = self._generate_copy(task_data, similar_ads, performance_data)

            # Generate image description (for image generation API)
            image_prompt = self._generate_image_prompt(task_data, similar_ads)

            # Cache the creative
            creative_id = f"creative_{datetime.now().timestamp()}"
            creative_data = {
                'id': creative_id,
                'copy': copy,
                'image_prompt': image_prompt,
                'similar_ads': similar_ads,
                'task_data': task_data,
                'timestamp': datetime.now().isoformat()
            }

            redis_client.setex(
                f'creative:{creative_id}',
                config['redis']['ttl'],
                json.dumps(creative_data)
            )

            logger.info(f"Generated creative: {creative_id}")

            return {
                'status': 'success',
                'creative_id': creative_id,
                'copy': copy,
                'image_prompt': image_prompt,
                'metadata': {
                    'similar_ads_count': len(similar_ads),
                    'has_performance_data': bool(performance_data)
                }
            }

        except Exception as e:
            logger.error(f"Error generating creative: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def _find_similar_ads(self, target_audience: Optional[Dict]) -> List[Dict]:
        """Find similar successful ads from RAG system"""
        try:
            # Query RAG for similar ads
            # This would use vector similarity search in production
            query = json.dumps(target_audience) if target_audience else "general"

            # Simulate RAG query - in production, use vector DB
            similar_keys = redis_client.keys('creative:*')[:5]
            similar_ads = []

            for key in similar_keys:
                data = redis_client.get(key)
                if data:
                    similar_ads.append(json.loads(data))

            return similar_ads

        except Exception as e:
            logger.error(f"Error finding similar ads: {str(e)}")
            return []

    def _get_performance_data(self, campaign_id: Optional[str]) -> Optional[Dict]:
        """Get historical performance data from cache"""
        if not campaign_id:
            return None

        try:
            data = redis_client.get(f'performance:{campaign_id}')
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Error getting performance data: {str(e)}")
            return None

    def _generate_copy(self, task_data: Dict, similar_ads: List[Dict],
                      performance_data: Optional[Dict]) -> str:
        """Generate ad copy using GPT-5.4-Nano"""
        try:
            # Prepare context
            context = {
                'task': task_data,
                'similar_ads': similar_ads[:3],  # Top 3 similar ads
                'performance': performance_data
            }

            prompt = f"""Generate compelling ad copy for Facebook Ads.

Task Requirements:
{json.dumps(task_data, indent=2)}

Top Performing Similar Ads:
{json.dumps([ad.get('copy', '') for ad in similar_ads[:3]], indent=2)}

Historical Performance Data:
{json.dumps(performance_data, indent=2) if performance_data else 'No historical data'}

Generate ad copy that:
1. Is clear and concise (under 125 characters for headline, under 125 for primary text)
2. Has a strong call-to-action
3. Addresses the target audience's pain points
4. Is optimized for 1-day click/view conversions
5. Follows best practices from successful similar ads

Return ONLY a JSON object with: headline, primary_text, description, cta
"""

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert copywriter specializing in high-converting Facebook ads. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            copy_json = json.loads(response.choices[0].message.content)
            return copy_json

        except Exception as e:
            logger.error(f"Error generating copy: {str(e)}")
            return {
                'headline': 'Error generating headline',
                'primary_text': 'Error generating primary text',
                'description': 'Error generating description',
                'cta': 'LEARN_MORE'
            }

    def _generate_image_prompt(self, task_data: Dict, similar_ads: List[Dict]) -> str:
        """Generate image prompt for image generation API"""
        try:
            # Extract visual elements from similar ads
            visual_elements = []
            for ad in similar_ads[:3]:
                if 'image_prompt' in ad:
                    visual_elements.append(ad['image_prompt'])

            prompt = f"""Generate an image prompt for a Facebook ad image.

Product/Service: {task_data.get('product', 'Unknown')}
Target Audience: {json.dumps(task_data.get('target_audience', {}))}
Successful Visual Elements: {', '.join(visual_elements) if visual_elements else 'None'}

Create a professional, eye-catching image prompt that:
1. Represents the product/service
2. Appeals to the target audience
3. Follows visual best practices
4. Is suitable for Facebook Ads

Return a single, detailed image prompt (max 200 characters).
"""

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert in visual design for advertising."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=200
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating image prompt: {str(e)}")
            return "Professional product image with clean background"

# Initialize agent
agent = CreativeAgent()

@app.route('/creative-agent', methods=['POST'])
def handle_request():
    """Handle incoming requests from orchestrator"""
    try:
        task_data = request.json
        logger.info(f"Received task: {task_data}")

        # Process based on task type
        task_type = task_data.get('task_type', 'generate_creative')

        if task_type == 'generate_creative':
            result = agent.generate_creative(task_data)
        else:
            result = {
                'status': 'error',
                'error': f'Unknown task type: {task_type}'
            }

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error handling request: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'agent': 'creative_agent',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = config['subagents']['creative_agent']['port']
    logger.info(f"Starting Creative Agent on port {port}")
    app.run(host='0.0.0.0', port=port)
