import torch
from frozen_discriminator import PerplexityCalculator
from transformers import GPT2LMHeadModel, GPT2Tokenizer, GPT2Config, AutoTokenizer, AutoModelForCausalLM


class AutoEncoderLLM(torch.nn.Module):
    def __init__(self, encoder, decoder, perplexity_calculator):
        super().__init__()
        self.encoder = encoder
        self.decoder = decoder
        # prepare perplexity calculator. keep it frozen!
        # self.perplexity_calculator = perplexity_calculator
        # Ensure perplexity_calculator remains frozen
        # for param in self.perplexity_calculator.parameters():
        #     param.requires_grad = False

    def _encode(self, **enc_inputs):
        return self.encoder(**enc_inputs)

    def _decode(self, **decoder_inps):
        return self.decoder(**decoder_inps)

    def forward(self, recon_target, encoder_target, **enc_inputs):
        encoder_outputs = self._encode(**enc_inputs, labels=encoder_target)
        decoder_outputs = self._decode(inputs_embeds=encoder_outputs.hidden_states[-1], labels=recon_target)
        # self.perplexity_calculator.eval() # should be but deepspeed complains!
        # log_perplexity_loss = self.perplexity_calculator(encoder_outputs.logits)
        log_perplexity_loss = 0
        return encoder_outputs, decoder_outputs, log_perplexity_loss


def load_model(model_name, wait_token='<w>', use_pretrained=True):
    """
    Load a model with the option to initialize with pretrained weights or randomly.

    Args:
    model_name (str): The name of the model to load (e.g., 'gpt2', 'llama-2').
    use_pretrained (bool): Whether to load the model with pretrained weights. If False, initializes with random weights.

    Returns:
    tuple: A tuple containing the tokenizer and the model.
    """
    if "llama" in model_name.lower():
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        perplexity_calculator = PerplexityCalculator(AutoModelForCausalLM.from_pretrained(model_name))
        if use_pretrained:
            encoder = AutoModelForCausalLM.from_pretrained(model_name)
            decoder = AutoModelForCausalLM.from_pretrained(model_name)
        else:
            # Load model with configuration from a pretrained model but without the pretrained weights
            config = AutoModelForCausalLM.from_pretrained(model_name).config
            encoder = AutoModelForCausalLM(config)
            decoder = AutoModelForCausalLM(config)
    elif "gpt2" in model_name.lower():  # Default to GPT2
        tokenizer = GPT2Tokenizer.from_pretrained(model_name)
        perplexity_calculator = PerplexityCalculator(GPT2LMHeadModel.from_pretrained(model_name))
        if use_pretrained:
            encoder = GPT2LMHeadModel.from_pretrained(model_name)
            decoder = GPT2LMHeadModel.from_pretrained(model_name)
        else:
            # Initialize GPT2 with random weights using its configuration
            config = GPT2Config()
            encoder = GPT2LMHeadModel(config)
            decoder = GPT2LMHeadModel(config)
    else:
        raise ValueError("Model name must contain 'llama' or 'gpt2'.")

    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.add_tokens([wait_token])  # add a special wait token
    wait_id = tokenizer.convert_tokens_to_ids(wait_token)

    encoder.resize_token_embeddings(len(tokenizer))
    decoder.resize_token_embeddings(len(tokenizer))

    perplexity_calculator = None  # TODO: remove this line
    return AutoEncoderLLM(encoder, decoder, perplexity_calculator), tokenizer, wait_id
