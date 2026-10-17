
def sortArray(cards):
    sortedArrays = {
        '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
        'Jack': 11, 'King': 12, 'Queen': 13, 'Ace': 14
    }
    
    return sorted(cards, key=lambda card: sortedArrays[str(card)])

cards = ['Jack', 8, 2, 2, 6, 'King', 5, 3, 'Queen', 'King', 'Queen']
sorted_cards = sortArray(cards)